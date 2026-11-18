"""check-toolchain.py holds each dune project it is given to the pins in toolchain.json, and names every project that disagrees."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

OCAML = Path(__file__).resolve().parents[1] / "ocaml"
SCRIPT = OCAML / "check-toolchain.py"
PINS = json.loads((OCAML / "toolchain.json").read_text())


def check(*arguments):
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True)


class CheckToolchain(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def project(self, name, *, ocaml=PINS["ocaml"], formatter_library=None):
        root = self.base / name
        root.mkdir()
        lang = ".".join(PINS["dune"].split(".")[:2])
        library = f"\n  (ocamlformat-lib (= {formatter_library}))" if formatter_library else ""
        (root / "dune-project").write_text(
            f"(lang dune {lang})\n(package\n (name {name})\n (depends\n  (ocaml (= {ocaml})){library}\n"
            f"  (ocamlformat (and :with-test (= {PINS['ocamlformat']})))))\n")
        (root / "dune-workspace").write_text(
            f"(lang dune {lang})\n"
            f"(repository (name pinned) (url \"git+https://github.com/ocaml/opam-repository.git#{PINS['opamRepository']}\"))\n"
            f"(repository (name pinned-overlay) (url \"git+https://github.com/ocaml-dune/opam-overlays.git#{PINS['duneOverlay']}\"))\n")
        (root / ".ocamlformat").write_text(f"version={PINS['ocamlformat']}\n")
        return root

    def test_projects_on_the_pins_agree(self):
        result = check(str(self.project("one")), str(self.project("two", formatter_library=PINS["ocamlformat"])))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_project_that_disagrees_is_named(self):
        result = check(str(self.project("one", ocaml="5.0.0")), str(self.project("two")),
                       str(self.project("three", formatter_library="0.1.0")))
        self.assertEqual(result.returncode, 1)
        self.assertIn("one: the compiler is ['5.0.0']", result.stderr)
        self.assertIn("three: ocamlformat-lib is ['0.1.0']", result.stderr)
        self.assertNotIn("two:", result.stderr)

    def test_the_base_image_is_the_pinned_one(self):
        result = check("--base-image")
        self.assertEqual(result.stdout.strip(), PINS["baseImage"])

    def test_no_project_is_a_usage_error(self):
        self.assertNotEqual(check().returncode, 0)


if __name__ == "__main__":
    unittest.main()
