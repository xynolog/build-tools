#!/usr/bin/env python3
"""Point a package.json at the npm tarballs of a verified SDK artifact bundle.

    python3 build-tools/prepare-sdk-package.py <bundle directory> <package.json>

Every npm package the bundle's artifacts.json lists becomes a `file:`
dependency on its tarball, by a path relative to the package.json, so it
resolves wherever the two are mounted with the same layout.

A package the package.json lists stays in the section that lists it,
`dependencies` or `devDependencies`. The bundle's other packages are what the
listed ones require of each other, so they join the listed ones: in
`devDependencies` when the package.json needs the SDK only to develop and
test, else in `dependencies`.
"""

import json
import os
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: prepare-sdk-package.py BUNDLE_DIR PACKAGE_JSON")
    bundle = Path(sys.argv[1]).resolve()
    package_path = Path(sys.argv[2]).resolve()

    manifest = json.loads((bundle / "artifacts.json").read_text())
    package = json.loads(package_path.read_text())
    npm_artifacts = [artifact for artifact in manifest["artifacts"] if artifact["ecosystem"] == "npm"]
    if not npm_artifacts:
        raise SystemExit("SDK artifact bundle contains no npm packages")

    names = {artifact["package"] for artifact in npm_artifacts}
    listed = {
        section: names & set(package.get(section, {}))
        for section in ("dependencies", "devDependencies")
    }
    both = listed["dependencies"] & listed["devDependencies"]
    if both:
        raise SystemExit(f"package.json lists {', '.join(sorted(both))} in both dependencies and devDependencies")
    rest = "devDependencies" if listed["devDependencies"] and not listed["dependencies"] else "dependencies"

    for artifact in npm_artifacts:
        tarball = bundle / artifact["path"]
        if not tarball.is_file():
            raise SystemExit(f"SDK npm artifact is missing: {tarball}")
        relative = Path(os.path.relpath(tarball, package_path.parent)).as_posix()
        name = artifact["package"]
        section = next((section for section, members in listed.items() if name in members), rest)
        package.setdefault(section, {})[name] = f"file:{relative}"

    package_path.write_text(json.dumps(package, indent=2) + "\n")


if __name__ == "__main__":
    main()
