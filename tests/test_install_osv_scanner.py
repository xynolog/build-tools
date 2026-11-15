"""install-osv-scanner.sh installs nothing it cannot match to the recorded checksum."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "install-osv-scanner.sh"


class InstallOsvScanner(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.bin = base / "bin"
        self.bin.mkdir()
        self.destination = base / "installed"
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}"}

    def stub(self, name, body):
        command = self.bin / name
        command.write_text(f"#!/bin/sh\n{body}\n")
        command.chmod(0o755)

    def install(self):
        return subprocess.run(["bash", str(SCRIPT), str(self.destination)], capture_output=True, text=True,
                              env=self.env)

    def test_refuses_a_download_whose_checksum_differs(self):
        self.stub("uname", 'case "$1" in -s) echo Linux ;; -m) echo x86_64 ;; esac')
        self.stub("curl", 'while [ "$1" != --output ]; do shift; done; printf "not the release" > "$2"')
        result = self.install()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not the 160c6253", result.stderr)
        self.assertFalse((self.destination / "osv-scanner").exists())

    def test_refuses_a_platform_with_no_release(self):
        self.stub("uname", 'case "$1" in -s) echo Plan9 ;; -m) echo mips ;; esac')
        result = self.install()
        self.assertEqual(result.returncode, 2)
        self.assertIn("No osv-scanner", result.stderr)


if __name__ == "__main__":
    unittest.main()
