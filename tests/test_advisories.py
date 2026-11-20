"""advisories.py fails on every unjudged finding and every stale ignore, against a stand-in osv-scanner."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "advisories.py"

# The stand-in prints REPORT, rewriting each source path from its basename to
# the path it was handed, records its arguments, and exits with EXIT.
SCANNER = """#!{python}
import json, os, sys
arguments = sys.argv[1:]
open(os.environ["CALLS"], "w").write(json.dumps(arguments))
open(os.environ["CALLS"] + ".config", "w").write(open(arguments[arguments.index("--config") + 1]).read())
handed = [arguments[i + 1] for i, a in enumerate(arguments) if a == "--lockfile"]
report = json.loads(os.environ["REPORT"])
for result in report.get("results", []):
    base = result["source"]["path"]
    result["source"]["path"] = next(p for p in handed if os.path.basename(p) == base)
print(json.dumps(report))
sys.exit(int(os.environ["EXIT"]))
"""


def finding(lockfile, name, version, *advisories):
    """One package with each advisory its own group: (id, aliases)."""
    return {
        "source": {"path": lockfile},
        "packages": [{
            "package": {"name": name, "version": version, "ecosystem": "npm"},
            "vulnerabilities": [{"id": id, "aliases": aliases, "summary": f"{id} summary"} for id, aliases in advisories],
            "groups": [{"ids": [id]} for id, _ in advisories],
        }],
    }


class Advisories(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "repository"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.bin = base / "bin"
        self.bin.mkdir()
        scanner = self.bin / "osv-scanner"
        scanner.write_text(SCANNER.format(python=sys.executable))
        scanner.chmod(0o755)
        self.calls = base / "calls"
        self.track("package-lock.json", "{}")
        self.write("advisories.toml", "")

    def write(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    def track(self, path, text):
        self.write(path, text)
        subprocess.run(["git", "-C", str(self.root), "add", path], check=True)

    def run_script(self, *results, exit=None, arguments=()):
        report = {"results": list(results)}
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "CALLS": str(self.calls),
               "REPORT": json.dumps(report), "EXIT": str(exit if exit is not None else (1 if results else 0))}
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *arguments],
                              capture_output=True, text=True, env=env)

    def handed(self):
        arguments = json.loads(self.calls.read_text())
        return [arguments[i + 1] for i, a in enumerate(arguments) if a == "--lockfile"]

    def test_passes_when_nothing_is_found(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fails_on_a_finding_no_ignore_names(self):
        result = self.run_script(finding("package-lock.json", "lodash", "4.17.15", ("GHSA-p6mc-m468-83gw", [])))
        self.assertEqual(result.returncode, 1)
        self.assertIn("lodash 4.17.15: GHSA-p6mc-m468-83gw", result.stderr)

    def test_an_ignore_names_a_finding_by_an_alias(self):
        self.write("advisories.toml", '[[ignore]]\nid = "CVE-2020-8203"\nreason = "Not reachable."\n')
        result = self.run_script(finding("package-lock.json", "lodash", "4.17.15",
                                         ("GHSA-p6mc-m468-83gw", ["CVE-2020-8203"])))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fails_on_an_ignore_that_matched_nothing(self):
        self.write("advisories.toml", '[[ignore]]\nid = "GHSA-gone-gone-gone"\nreason = "Was not reachable."\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("GHSA-gone-gone-gone", result.stderr)

    def test_one_ignore_leaves_the_other_findings_failing(self):
        self.write("advisories.toml", '[[ignore]]\nid = "GHSA-aaaa-aaaa-aaaa"\nreason = "Not reachable."\n')
        result = self.run_script(finding("package-lock.json", "lodash", "4.17.15",
                                         ("GHSA-aaaa-aaaa-aaaa", []), ("GHSA-bbbb-bbbb-bbbb", [])))
        self.assertEqual(result.returncode, 1)
        self.assertIn("GHSA-bbbb-bbbb-bbbb", result.stderr)
        self.assertNotIn("matched no finding", result.stderr)

    def test_refuses_an_ignore_without_a_reason(self):
        self.write("advisories.toml", '[[ignore]]\nid = "GHSA-p6mc-m468-83gw"\nreason = " "\n')
        result = self.run_script(finding("package-lock.json", "lodash", "4.17.15", ("GHSA-p6mc-m468-83gw", [])))
        self.assertEqual(result.returncode, 1)
        self.assertIn("non-empty id and reason", result.stderr)

    def test_refuses_a_repository_without_advisories_toml(self):
        (self.root / "advisories.toml").unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("advisories.toml is missing", result.stderr)

    def test_fails_when_the_scanner_fails(self):
        result = self.run_script(exit=127)
        self.assertEqual(result.returncode, 1)
        self.assertIn("osv-scanner failed (exit 127)", result.stderr)

    def test_scans_every_tracked_lockfile_and_each_named_one_and_no_other(self):
        for path in ("rust/Cargo.lock", "go/go.mod", "python/uv.lock", "csharp/packages.lock.json",
                     "kotlin/gradle.lockfile", "haskell/cabal.project.freeze"):
            self.track(path, "")
        self.write("untracked/package-lock.json", "{}")
        resolved = self.write("typescript/package-lock.json", "{}")
        result = self.run_script(arguments=("--lockfile", str(resolved)))
        self.assertEqual(result.returncode, 0, result.stderr)
        root = self.root.resolve()
        self.assertEqual(sorted(self.handed()), sorted(str(root / path) for path in (
            "package-lock.json", "rust/Cargo.lock", "go/go.mod", "python/uv.lock", "csharp/packages.lock.json",
            "kotlin/gradle.lockfile", "haskell/cabal.project.freeze", "typescript/package-lock.json")))

    def test_hands_package_resolved_over_as_it_is(self):
        self.track("swift/Package.resolved", json.dumps({"version": 3, "pins": [{
            "identity": "swift-nio", "kind": "remoteSourceControl",
            "location": "https://github.com/apple/swift-nio.git",
            "state": {"revision": "0" * 40, "version": "2.29.0"}}]}))
        result = self.run_script(finding("Package.resolved", "github.com/apple/swift-nio", "2.29.0",
                                         ("GHSA-7fj7-39wj-c64f", [])))
        self.assertEqual(result.returncode, 1)
        self.assertIn("swift/Package.resolved: github.com/apple/swift-nio 2.29.0: GHSA-7fj7-39wj-c64f", result.stderr)
        self.assertEqual(self.handed(), [str(self.root.resolve() / "package-lock.json"),
                                         str(self.root.resolve() / "swift/Package.resolved")])

    def test_refuses_a_swift_pin_without_a_version(self):
        self.track("swift/Package.resolved", json.dumps({"version": 2, "pins": [{
            "identity": "swift-nio", "kind": "remoteSourceControl",
            "location": "https://github.com/apple/swift-nio.git", "state": {"revision": "0" * 40}}]}))
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("pinned to a revision", result.stderr)

    def test_runs_the_scanner_with_an_empty_configuration(self):
        self.write("osv-scanner.toml", '[[IgnoredVulns]]\nid = "GHSA-p6mc-m468-83gw"\n')
        self.run_script()
        self.assertEqual(Path(str(self.calls) + ".config").read_text(), "")

    def test_refuses_a_dune_package_without_its_version(self):
        self.track("ocaml/dune.lock/lock.dune", "(lang package 0.1)\n")
        self.track("ocaml/dune.lock/tls.2.0.0.pkg", "(build (run dune build))\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("tls.2.0.0.pkg: states 0 versions, not one.", result.stderr)

    def test_refuses_a_dune_package_named_for_another_version(self):
        self.track("ocaml/dune.lock/lock.dune", "(lang package 0.1)\n")
        self.track("ocaml/dune.lock/tls.2.0.0.pkg", "(version 2.1.0)\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("tls.2.0.0.pkg: states version 2.1.0, and its name is not <package>.2.1.0.pkg.", result.stderr)

    def test_refuses_a_dune_lock_that_pins_nothing(self):
        self.track("ocaml/dune.lock/lock.dune", "(lang package 0.1)\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("ocaml/dune.lock pins no package.", result.stderr)

    def test_hands_no_dune_lock_to_the_scanner(self):
        self.track("ocaml/dune.lock/lock.dune", "(lang package 0.1)\n")
        self.run_script()
        self.assertEqual(self.handed(), [str(self.root.resolve() / "package-lock.json")])


if __name__ == "__main__":
    unittest.main()
