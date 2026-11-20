"""advisories.py, with the real osv-scanner and OSV's API, finds a known advisory in every lockfile format the repositories use.

Each fixture pins one package at a version OSV records an advisory for
(checked against api.osv.dev when the fixture was chosen). A format the
scanner stops reading, or this script stops handing it, fails here. It needs
osv-scanner on PATH and the network, so CI runs it after
install-osv-scanner.sh, not with the unit tests:

    python3 tests/live_osv_scanner.py -v
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "advisories.py"

# lockfile path: (its text, the package the scanner has to report)
FIXTURES = {
    "npm/package-lock.json": (json.dumps({
        "name": "fixture", "version": "1.0.0", "lockfileVersion": 3, "requires": True,
        "packages": {
            "": {"name": "fixture", "version": "1.0.0", "dependencies": {"lodash": "4.17.15"}},
            "node_modules/lodash": {"version": "4.17.15",
                                    "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.15.tgz"},
        },
    }), "lodash 4.17.15"),
    "rust/Cargo.lock": ("""version = 3

[[package]]
name = "fixture"
version = "0.1.0"
dependencies = ["time"]

[[package]]
name = "time"
version = "0.1.42"
source = "registry+https://github.com/rust-lang/crates.io-index"
""", "time 0.1.42"),
    "go/go.mod": ("""module example.com/fixture

go 1.25

require golang.org/x/text v0.3.0
""", "golang.org/x/text 0.3.0"),
    "python/uv.lock": ("""version = 1
requires-python = ">=3.12"

[[package]]
name = "urllib3"
version = "1.26.4"
source = { registry = "https://pypi.org/simple" }
""", "urllib3 1.26.4"),
    "csharp/packages.lock.json": (json.dumps({"version": 1, "dependencies": {"net8.0": {"Newtonsoft.Json": {
        "type": "Direct", "requested": "[12.0.1, )", "resolved": "12.0.1",
        "contentHash": "pBR3wCgYWZGiaZDYP+HHYnalVnPJlpP1q55qvVb+adrDHmFMDc1NAKio61xTwftK3Pw5h7TZJPJEEVMd6ty8rg=="}}}}),
        "Newtonsoft.Json 12.0.1"),
    "kotlin/gradle.lockfile": ("""# This is a Gradle generated file for dependency locking.
org.apache.logging.log4j:log4j-api:2.14.1=runtimeClasspath
org.apache.logging.log4j:log4j-core:2.14.1=runtimeClasspath
empty=
""", "org.apache.logging.log4j:log4j-core 2.14.1"),
    "haskell/cabal.project.freeze": ("""active-repositories: hackage.haskell.org:merge
constraints: any.aeson ==1.5.6.0,
             any.base ==4.14.3.0
index-state: hackage.haskell.org 2026-01-01T00:00:00Z
""", "aeson 1.5.6.0"),
    "swift/Package.resolved": (json.dumps({"version": 3, "pins": [{
        "identity": "swift-nio", "kind": "remoteSourceControl",
        "location": "https://github.com/apple/swift-nio.git",
        "state": {"revision": "d1690f85419fdac8d54e350fb6d2ab9fd95afd75", "version": "2.29.0"}}]}),
        "github.com/apple/swift-nio 2.29.0"),
}

# A dune package lock, which advisories.py asks OSV's API about itself: the
# directory, its files, and the package it has to report.
DUNE_LOCK = ("ocaml/dune.lock", {
    "ocaml/dune.lock/lock.dune": "(lang package 0.1)\n",
    "ocaml/dune.lock/tls.2.0.0.pkg": "(version 2.0.0)\n",
}, "tls 2.0.0")

# A package with no advisory, so a clean scan is seen to pass.
CLEAN = json.dumps({
    "name": "fixture", "version": "1.0.0", "lockfileVersion": 3, "requires": True,
    "packages": {
        "": {"name": "fixture", "version": "1.0.0", "dependencies": {"is-number": "7.0.0"}},
        "node_modules/is-number": {"version": "7.0.0",
                                   "resolved": "https://registry.npmjs.org/is-number/-/is-number-7.0.0.tgz"},
    },
})


def repository(directory, files):
    root = Path(directory)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "advisories.toml").write_text("")
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    return root


def advisories(root):
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True)


class RealScanner(unittest.TestCase):
    def test_finds_an_advisory_in_every_lockfile_format(self):
        with tempfile.TemporaryDirectory() as directory:
            lock, files, locked = DUNE_LOCK
            root = repository(directory, {**{path: text for path, (text, _) in FIXTURES.items()}, **files})
            result = advisories(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for path, package in [*((path, package) for path, (_, package) in FIXTURES.items()), (lock, locked)]:
            with self.subTest(path=path):
                self.assertIn(f"  {path}: {package}: ", result.stderr)

    def test_passes_a_lockfile_with_no_advisory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = advisories(repository(directory, {"package-lock.json": CLEAN}))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_passes_a_dune_lock_with_no_advisory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = advisories(repository(directory, {"dune.lock/lock.dune": "(lang package 0.1)\n",
                                                       "dune.lock/yojson.3.0.0.pkg": "(version 3.0.0)\n"}))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
