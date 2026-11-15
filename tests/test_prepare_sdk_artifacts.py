"""prepare-sdk-artifacts.sh refuses to build against anything but the pinned Protocol, and says
where the SDK has to come from."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "prepare-sdk-artifacts.sh"
# The fixtures' commits are made with no user or system git configuration, so the
# machine's own (a signer, hooks) has no say in them.
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
}


def git(*arguments, cwd):
    return subprocess.run(["git", *arguments], cwd=cwd, env=GIT_ENV, check=True, capture_output=True, text=True).stdout.strip()


class PrepareSdkArtifacts(unittest.TestCase):
    def consumer(self, pinned_to_protocol_head=True):
        """A repository with a protocol submodule and build-tools at build-tools/."""
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        protocol = root / "protocol"
        protocol.mkdir()
        git("init", "-q", cwd=protocol)
        (protocol / "VERSION").write_text("0.0.0\n")
        git("add", "VERSION", cwd=protocol)
        git("commit", "-q", "-m", "protocol", cwd=protocol)
        head = git("rev-parse", "HEAD", cwd=protocol)
        pin = head if pinned_to_protocol_head else "0" * 39 + "1"
        git("init", "-q", cwd=root)
        git("update-index", "--add", "--cacheinfo", f"160000,{pin},protocol", cwd=root)
        git("commit", "-q", "-m", "consumer", cwd=root)
        (root / "build-tools").mkdir()
        shutil.copy(SCRIPT, root / "build-tools" / SCRIPT.name)
        return root

    def run_script(self, root, **environment):
        env = {key: value for key, value in os.environ.items() if key not in ("SDK_ARTIFACTS", "SDK_REPO")}
        return subprocess.run(
            ["bash", str(root / "build-tools" / SCRIPT.name), "go"],
            env={**env, **environment}, capture_output=True, text=True, timeout=30,
        )

    def test_refuses_a_protocol_checkout_that_is_not_the_pin(self):
        result = self.run_script(self.consumer(pinned_to_protocol_head=False))
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not match this repository's pin", result.stderr)

    def test_without_a_bundle_or_an_sdk_checkout_names_both(self):
        result = self.run_script(self.consumer())
        self.assertEqual(result.returncode, 2)
        self.assertIn("Set SDK_REPO to an SDK checkout, or SDK_ARTIFACTS to an artifact bundle.", result.stderr)

    def test_an_sdk_checkout_that_is_not_there_is_named(self):
        root = self.consumer()
        result = self.run_script(root, SDK_REPO=str(root / "no-sdk"))
        self.assertEqual(result.returncode, 2)
        self.assertIn(f"SDK checkout not found at {root / 'no-sdk'}", result.stderr)


if __name__ == "__main__":
    unittest.main()
