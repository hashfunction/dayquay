"""Verify actual checkout bytes across Windows and MSYS Git defaults."""

from pathlib import Path
import subprocess
import tempfile
import unittest


class CheckoutTests(unittest.TestCase):
    def test_tracked_policy_keeps_both_git_runtimes_clean_without_hiding_changes(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()

            def git(*args, at=source):
                return subprocess.check_output(["git", "-C", str(at), *args])

            git("init", "-q")
            git("config", "user.name", "Checkout Fixture")
            git("config", "user.email", "fixture@example.invalid")
            git("config", "core.autocrlf", "false")
            (source / ".gitattributes").write_bytes(
                (root / ".gitattributes").read_bytes()
            )
            (source / "source.py").write_bytes(b"# exact source\nvalue = 1\n")
            (source / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00binary\r\n")
            git("add", ".")
            git("commit", "-qm", "fixture")
            clone = Path(directory) / "Windows checkout"
            git(
                "clone",
                "-q",
                "--no-local",
                "-c",
                "core.autocrlf=true",
                str(source),
                str(clone),
            )
            for filename in ("source.py", "image.png"):
                self.assertEqual(
                    (clone / filename).read_bytes(), (source / filename).read_bytes()
                )
            for autocrlf in ("true", "false"):
                git("config", "core.autocrlf", autocrlf, at=clone)
                self.assertEqual(
                    git("status", "--porcelain", "--untracked-files=all", at=clone), b""
                )
            (clone / "source.py").write_bytes(b"# actual change\n")
            (clone / "image.png").write_bytes(b"\x00changed binary")
            changes = git("status", "--porcelain", "--untracked-files=all", at=clone)
            self.assertIn(b" M source.py", changes)
            self.assertIn(b" M image.png", changes)


if __name__ == "__main__":
    unittest.main()
