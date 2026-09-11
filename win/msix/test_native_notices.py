"""Actual file notice collection tests. Fixtures do not qualify native licenses."""

import importlib.util
from pathlib import Path
import tempfile
import os
import subprocess
import unittest

try:
    spec = importlib.util.spec_from_file_location(
        "record_inventory", Path(__file__).parents[1] / "record-package-inventory.py"
    )
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
except FileNotFoundError:
    collector = None


class NoticeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(collector, "Native notice collector is not implemented")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.prefix = self.root / "ucrt64"
        notice = self.prefix / "share/licenses/python/LICENSE"
        notice.parent.mkdir(parents=True)
        notice.write_bytes(b"Original native Python copyright")
        self.release = self.root / "stage"
        self.release.mkdir()

    def test_collects_exact_notice_bytes_and_explicit_unresolved_audit(self):
        record = collector.collect_notices(self.prefix, self.release)
        self.assertEqual(
            (self.release / "_internal/notices/native/python/LICENSE").read_bytes(),
            b"Original native Python copyright",
        )
        self.assertTrue(record["unresolved"])
        self.assertFalse(record["inventoryIsLicenseClearance"])
        self.assertEqual(
            record["files"], collector.inventory_tree(self.release / "_internal/notices")
        )

    def test_refuses_prior_output_without_touching_it(self):
        output = self.release / "_internal/notices"
        output.mkdir(parents=True)
        marker = output / "owned"
        marker.write_bytes(b"preserve")
        with self.assertRaises(ValueError):
            collector.collect_notices(self.prefix, self.release)
        self.assertEqual(marker.read_bytes(), b"preserve")

    def test_refuses_linked_notice_sources(self):
        notice = self.prefix / "share/licenses/link"
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/d", "/c", "mklink", "/J", str(notice), str(self.root)],
                check=True,
                capture_output=True,
            )
        else:
            notice.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            collector.collect_notices(self.prefix, self.release)
        notice.rmdir() if os.name == "nt" else notice.unlink()
        self.assertFalse((self.release / "_internal/notices").exists())


if __name__ == "__main__":
    unittest.main()
