#!/usr/bin/env python3
"""Point a package.json at the npm tarballs of a verified SDK artifact bundle.

    python3 build-tools/prepare-sdk-package.py <bundle directory> <package.json>

Every npm package the bundle's artifacts.json lists becomes a `file:`
dependency on its tarball, by a path relative to the package.json, so it
resolves wherever the two are mounted with the same layout.
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

    for artifact in npm_artifacts:
        tarball = bundle / artifact["path"]
        if not tarball.is_file():
            raise SystemExit(f"SDK npm artifact is missing: {tarball}")
        relative = Path(os.path.relpath(tarball, package_path.parent)).as_posix()
        package["dependencies"][artifact["package"]] = f"file:{relative}"

    package_path.write_text(json.dumps(package, indent=2) + "\n")


if __name__ == "__main__":
    main()
