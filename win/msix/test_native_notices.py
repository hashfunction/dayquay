"""Actual file notice collection tests. Fixtures do not qualify native licenses."""

import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import os
import stat
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from junction_fixture import WindowsJunctionFixture

try:
    spec = importlib.util.spec_from_file_location(
        "record_inventory", Path(__file__).parents[1] / "record-package-inventory.py"
    )
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
except FileNotFoundError:
    collector = None


class NoticeTests(WindowsJunctionFixture, unittest.TestCase):
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

    def test_collects_all_original_supplement_bytes_beside_existing_notices(self):
        collector.collect_notices(self.prefix, self.release)
        output = self.release / "_internal/notices/supplement"
        self.assertTrue((output / "index.json").is_file(), "Original supplement was omitted")
        index = json.loads((output / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index["files"]), 648)
        original = Path(__file__).parents[1] / "notice-supplement"
        self.assertEqual(
            (output / "index.json").read_bytes(), (original / "index.json").read_bytes()
        )
        for name, expected in index["files"].items():
            data = (output / name).read_bytes()
            self.assertEqual(data, (original / name).read_bytes(), name)
            self.assertEqual(len(data), expected["bytes"], name)
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected["sha256"], name)
        self.assertEqual(
            (self.release / "_internal/notices/native/python/LICENSE").read_bytes(),
            b"Original native Python copyright",
        )

    def test_refuses_missing_corrupt_extra_or_mistyped_original_before_copying(self):
        for mutation in ("missing", "corrupt", "extra", "mistyped"):
            with self.subTest(mutation=mutation):
                supplement = self.root / mutation
                shutil.copytree(Path(__file__).parents[1] / "notice-supplement", supplement)
                original = supplement / "upstream/libyaml/License"
                if mutation == "missing":
                    original.unlink()
                elif mutation == "corrupt":
                    original.write_bytes(b"altered notice")
                elif mutation == "extra":
                    (supplement / "unindexed").write_bytes(b"extra")
                else:
                    path = supplement / "index.json"
                    index = json.loads(path.read_text(encoding="utf-8"))
                    index["files"]["upstream/libyaml/License"]["bytes"] = True
                    path.write_text(json.dumps(index), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "[Oo]riginal notice supplement"):
                    collector.collect_notices(self.prefix, self.release, supplement)
                self.assertFalse((self.release / "_internal/notices").exists())

    def test_detects_corrupted_copy_and_preserves_unrelated_stage_file(self):
        marker = self.release / "existing-resource"
        marker.write_bytes(b"preserve")
        copy_bytes = shutil.copyfileobj

        def corrupt_one_copy(source, destination):
            copy_bytes(source, destination)
            if Path(destination.name).as_posix().endswith("supplement/upstream/libyaml/License"):
                destination.write(b"corruption during copy")

        with patch.object(collector.shutil, "copyfileobj", side_effect=corrupt_one_copy):
            with self.assertRaisesRegex(ValueError, "supplement changed while copying"):
                collector.collect_notices(self.prefix, self.release)
        self.assertEqual(marker.read_bytes(), b"preserve")
        self.assertFalse((self.release / "_internal/notices").exists())

    def create_notice_link(self, notice):
        if os.name == "nt":
            self.create_windows_junction(notice, self.root)
        else:
            notice.symlink_to(self.root, target_is_directory=True)

    def test_notice_junction_uses_native_paths_from_actual_msys_failure(self):
        self.root = "D:/a/_temp/msys64/tmp/notice fixture"
        notice = self.root + "/ucrt64/share/licenses/link"
        with patch.object(sys.modules[__name__], "os", types.SimpleNamespace(name="nt")), patch(
            "subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")
        ) as run:
            self.create_notice_link(notice)
        self.assertEqual(
            run.call_args.args[0],
            [
                "cmd.exe",
                "/d",
                "/v:off",
                "/c",
                "mklink",
                "/J",
                r"D:\a\_temp\msys64\tmp\notice fixture\ucrt64\share\licenses\link",
                r"D:\a\_temp\msys64\tmp\notice fixture",
            ],
        )

    def test_refuses_linked_notice_sources(self):
        notice = self.prefix / "share/licenses/linked notices"
        self.create_notice_link(notice)
        try:
            if os.name == "nt":
                info = notice.lstat()
                self.assertTrue(info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
                self.assertEqual(info.st_reparse_tag, stat.IO_REPARSE_TAG_MOUNT_POINT)
            with self.assertRaisesRegex(ValueError, "Symlink/reparse point refused"):
                collector.collect_notices(self.prefix, self.release)
        finally:
            notice.rmdir() if os.name == "nt" else notice.unlink()
        self.assertFalse((self.release / "_internal/notices").exists())


if __name__ == "__main__":
    unittest.main()
