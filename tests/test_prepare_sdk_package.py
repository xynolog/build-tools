"""prepare-sdk-package.py points a package.json at the bundle's npm tarballs, from wherever the bundle is."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "prepare-sdk-package.py"


class PrepareSdkPackage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.package = self.base / "app" / "package.json"
        self.package.parent.mkdir()
        self.package.write_text(json.dumps({"name": "app", "dependencies": {"react": "19.0.0"}}))

    def bundle(self, directory, artifacts, tarballs):
        bundle = self.base / directory
        (bundle / "typescript").mkdir(parents=True)
        (bundle / "artifacts.json").write_text(json.dumps({"artifacts": artifacts}))
        for path in tarballs:
            (bundle / path).write_text("tarball")
        return bundle

    def prepare(self, bundle):
        return subprocess.run([sys.executable, str(SCRIPT), str(bundle), str(self.package)],
                              capture_output=True, text=True)

    def dependencies(self):
        return json.loads(self.package.read_text())["dependencies"]

    def test_a_bundle_beside_the_package_is_named_by_a_relative_path(self):
        bundle = self.bundle("app/.build/sdk-artifacts", [
            {"ecosystem": "npm", "package": "@xynolog/sdk", "path": "typescript/xynolog-sdk-1.0.0.tgz"},
            {"ecosystem": "go", "package": "github.com/xynolog/sdk/go", "path": "go/go-proxy"},
        ], ["typescript/xynolog-sdk-1.0.0.tgz"])
        result = self.prepare(bundle)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.dependencies(), {
            "react": "19.0.0", "@xynolog/sdk": "file:.build/sdk-artifacts/typescript/xynolog-sdk-1.0.0.tgz"})

    def test_a_bundle_mounted_elsewhere_is_named_by_a_path_up_and_across(self):
        bundle = self.bundle("sdk-bundle", [
            {"ecosystem": "npm", "package": "@xynolog/sdk", "path": "typescript/xynolog-sdk-1.0.0.tgz"},
        ], ["typescript/xynolog-sdk-1.0.0.tgz"])
        result = self.prepare(bundle)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.dependencies()["@xynolog/sdk"],
                         "file:../sdk-bundle/typescript/xynolog-sdk-1.0.0.tgz")

    def test_refuses_a_missing_tarball(self):
        bundle = self.bundle("sdk-bundle", [
            {"ecosystem": "npm", "package": "@xynolog/sdk", "path": "typescript/xynolog-sdk-1.0.0.tgz"},
        ], [])
        result = self.prepare(bundle)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SDK npm artifact is missing", result.stderr)

    def test_refuses_a_bundle_with_no_npm_package(self):
        bundle = self.bundle("sdk-bundle", [
            {"ecosystem": "go", "package": "github.com/xynolog/sdk/go", "path": "go/go-proxy"},
        ], [])
        result = self.prepare(bundle)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("contains no npm packages", result.stderr)


if __name__ == "__main__":
    unittest.main()
