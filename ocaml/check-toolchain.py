"""check-toolchain.py PROJECT...: hold each dune project to the OCaml toolchain's pins.

toolchain.json, beside this script, is the one statement of the pins: the
compiler, dune, ocamlformat, the opam repository and dune's overlay, and the
image they are built on. A project is a directory with its dune-project,
dune-workspace and .ocamlformat. Each must name the pinned compiler, dune's
language at the pinned dune's minor version, the pinned ocamlformat for its
tests, and the pinned repositories; a project that names ocamlformat-lib
names the pinned ocamlformat's. Every disagreement is printed, naming its
project, and any fails the run.

check-toolchain.py --base-image prints the image the pins are built on.
"""
import json
import re
import sys
from pathlib import Path

pins = json.loads((Path(__file__).resolve().parent / 'toolchain.json').read_text())


def disagreements(project_root):
    project = (project_root / 'dune-project').read_text()
    workspace = (project_root / 'dune-workspace').read_text()
    ocamlformat = (project_root / '.ocamlformat').read_text().strip()
    wanted = [
        ('the compiler', re.findall(r'\(ocaml \(= ([^)]+)\)\)', project), [pins['ocaml']]),
        ("dune's language", re.findall(r'\(lang dune ([^)]+)\)', project), ['.'.join(pins['dune'].split('.')[:2])]),
        ('ocamlformat', re.findall(r'\(ocamlformat \(and :with-test \(= ([^)]+)\)\)\)', project), [pins['ocamlformat']]),
        ('.ocamlformat', [ocamlformat], ['version=' + pins['ocamlformat']]),
        ('the opam repository', re.findall(r'git\+https://github.com/ocaml/opam-repository.git#([a-f0-9]+)', workspace), [pins['opamRepository']]),
        ("dune's overlay", re.findall(r'git\+https://github.com/ocaml-dune/opam-overlays.git#([a-f0-9]+)', workspace), [pins['duneOverlay']]),
    ]
    libraries = re.findall(r'\(ocamlformat-lib \(= ([^)]+)\)\)', project)
    if libraries:
        wanted.append(('ocamlformat-lib', libraries, [pins['ocamlformat']]))
    return [f'{project_root}: {what} is {found}, not {expected}'
            for what, found, expected in wanted if found != expected]


if sys.argv[1:] == ['--base-image']:
    print(pins['baseImage'])
elif not sys.argv[1:] or '--base-image' in sys.argv[1:]:
    raise SystemExit('usage: check-toolchain.py PROJECT... | --base-image')
else:
    failures = [failure for root in sys.argv[1:] for failure in disagreements(Path(root))]
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        raise SystemExit(1)
    print('OCaml toolchain constraints agree')
