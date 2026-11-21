"""toolchain-image.sh tags the toolchain's image by what it is built from, and builds it only when no image has that tag."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_check_toolchain import pinned_project

ROOT = Path(__file__).resolve().parents[1]


class ToolchainImage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        # A copy of the scripts, so a test can change what the image is built from.
        self.tools = base / "build-tools"
        shutil.copytree(ROOT / "ocaml", self.tools / "ocaml")
        shutil.copy(ROOT / "container-runtime.sh", self.tools)
        self.script = self.tools / "ocaml" / "toolchain-image.sh"
        self.project = pinned_project(base, "project")
        self.bin = base / "bin"
        self.bin.mkdir()
        self.log = base / "calls"
        self.images = base / "images"
        self.images.mkdir()
        # A Docker that has the images named by files in self.images.
        docker = self.bin / "docker"
        docker.write_text(
            f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{self.log}"\n'
            f'if [ "$1 $2" = "image inspect" ]; then test -e "{self.images}/$3"; fi\n')
        docker.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{self.bin}:/usr/bin:/bin", "CONTAINER_RUNTIME": "docker"}

    def run_script(self, *arguments):
        return subprocess.run(["/bin/bash", str(self.script), *arguments], env=self.env,
                              capture_output=True, text=True, timeout=60)

    def tag(self):
        result = self.run_script("--tag")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def calls(self):
        return [line for line in self.log.read_text().splitlines() if line != "info"]

    def test_the_tag_names_the_toolchain_image(self):
        self.assertRegex(self.tag(), r"^xynolog-ocaml-toolchain:[0-9a-f]{16}$")
        self.assertEqual(self.tag(), self.tag())

    def test_every_file_the_image_is_built_from_moves_the_tag(self):
        dockerfile = (self.tools / "ocaml" / "Dockerfile").read_text()
        copied = [source for line in dockerfile.splitlines()
                  if (match := re.match(r"(?:COPY|ADD)\s+(?:--\S+\s+)*(.+)", line))
                  for source in match.group(1).split()[:-1]]
        self.assertTrue(copied)
        for name in ["Dockerfile", *copied]:
            before = self.tag()
            with (self.tools / "ocaml" / name).open("a") as file:
                file.write("\n")
            self.assertNotEqual(self.tag(), before, name)

    def test_an_absent_image_is_built_under_its_tag(self):
        result = self.run_script(str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(calls[0], f"image inspect {self.tag()}")
        self.assertTrue(calls[1].startswith("build "), calls)
        self.assertIn(f"--tag {self.tag()} ", calls[1])
        self.assertEqual(calls[2:], [f"image tag {self.tag()} xynolog-ocaml-toolchain"])

    def test_a_present_image_is_used_as_it_is(self):
        (self.images / self.tag()).touch()
        result = self.run_script(str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [f"image inspect {self.tag()}",
                                        f"image tag {self.tag()} xynolog-ocaml-toolchain"])

    def test_a_project_off_the_pins_builds_nothing(self):
        (self.project / ".ocamlformat").write_text("version=0.1.0\n")
        result = self.run_script(str(self.project))
        self.assertEqual(result.returncode, 1)
        self.assertIn(".ocamlformat", result.stderr)
        self.assertFalse(self.log.exists())

    def test_tag_with_projects_is_a_usage_error(self):
        self.assertEqual(self.run_script("--tag", str(self.project)).returncode, 2)
        self.assertEqual(self.run_script().returncode, 2)


if __name__ == "__main__":
    unittest.main()
