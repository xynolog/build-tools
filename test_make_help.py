"""make help lists every public target and nothing else, and refuses an entry without its text.

Run from a repository that has build-tools at build-tools/:

    python3 build-tools/test_make_help.py --root . [--list '<placeholder>=VARIABLE' ...]

A `--list` says which Makefile variable an entry's `<placeholder>` stands for:
the entry names one target per word of that variable.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT: Path
LISTS: dict[str, str]


def make(*arguments, cwd):
    return subprocess.run(["make", "-s", *arguments], cwd=cwd, capture_output=True, text=True)


def database():
    """The Makefile as make reads it, every variable and `.PHONY` expanded."""
    return subprocess.run(
        ["make", "-pRrq", "-f", "Makefile", ":"], cwd=ROOT, capture_output=True, text=True
    ).stdout


class MakeHelp(unittest.TestCase):
    def test_lists_every_public_target_and_nothing_else(self):
        result = make("help", cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        read = database()
        variables = dict(re.findall(r"^([A-Z][A-Z0-9_]*) :?= (.*)$", read, re.M))
        listed = set()
        for line in result.stdout.splitlines():
            named = re.match(r"  ([a-z<]\S*)", line)
            if not named:
                continue
            name = named[1]
            placeholder = next((p for p in LISTS if p in name), None)
            if placeholder is None:
                listed.add(name)
            else:
                words = variables[LISTS[placeholder]].split()
                listed |= {name.replace(placeholder, word) for word in words}
        phony = set(re.search(r"^\.PHONY: (.*)$", read, re.M)[1].split())
        self.assertEqual(listed, phony - {"help"})

    def test_refuses_an_entry_without_its_text(self):
        with tempfile.TemporaryDirectory() as scratch:
            copy = Path(scratch)
            (copy / "build-tools").mkdir()
            shutil.copy(HERE / "make-help.awk", copy / "build-tools" / "make-help.awk")
            makefile = (ROOT / "Makefile").read_text()
            (copy / "Makefile").write_text(makefile + "## clean Remove everything\n")
            result = make("help", cwd=copy)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("clean Remove everything", result.stderr)


def placeholder_list(text):
    placeholder, equals, variable = text.partition("=")
    if not (equals and placeholder.startswith("<") and placeholder.endswith(">") and variable):
        raise argparse.ArgumentTypeError(f"expected '<placeholder>=VARIABLE', got {text!r}")
    return placeholder, variable


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, required=True, help="the repository whose Makefile is checked")
    parser.add_argument("--list", type=placeholder_list, action="append", default=[], dest="lists")
    known, rest = parser.parse_known_args()
    ROOT = known.root.resolve()
    LISTS = dict(known.lists)
    unittest.main(argv=[sys.argv[0], *rest])
