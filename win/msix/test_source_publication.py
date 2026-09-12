"""Mutate the actual reviewed source boundary without downloading binaries."""
# Copyright 2026 Trieflow LLC. MIT.
import copy
import json
from pathlib import Path
import unittest

from msix_qualification import source_inputs
from source_publication import validate_native_closure


class NativeSourcePublicationTests(unittest.TestCase):
    def setUp(self):
        self.closure = json.loads(Path(__file__).with_name("native-source-publication.json").read_text())
        c = self.closure
        self.record = {"identity": {"executable": "Jotmorrow.exe", "version": "1.0.1.0"},
                       "buildProvenance": {"nativeInputs": {"archives": copy.deepcopy(c["native_archives"]),
                                                           "installedVersions": copy.deepcopy(c["installed_native_versions"])}},
                       "releaseInput": {**copy.deepcopy(c["vendor_payload"]), **copy.deepcopy(c["original_notice_payload"])},
                       "sourceInputs": {**copy.deepcopy(c["current_application"]["source_inputs"]), "win/notice-supplement/index.json": copy.deepcopy(c["notice_supplement_index"])}}

    def test_complete_actual_reviewed_boundary_matches(self):
        result = validate_native_closure(self.closure, self.record)
        self.assertEqual((result["native_archives"], result["native_versions"], result["mapped_vendor_files"]), (178, 89, 1165))
        self.assertEqual(result["original_notice_files"], 766)

    def test_current_application_binding_matches_actual_source_files(self):
        actual = source_inputs(Path(__file__).resolve().parents[2])
        self.assertEqual(
            {path: value for path, value in actual.items() if not path.startswith("win/notice-supplement/")},
            self.closure["current_application"]["source_inputs"],
        )

    def test_native_source_and_notice_mutations_fail_closed(self):
        for mutation in ("archive", "version", "vendor", "notice", "index", "extra-dll", "extra-exe", "audit", "release", "application-source", "application-version"):
            with self.subTest(mutation=mutation):
                c, r = copy.deepcopy(self.closure), copy.deepcopy(self.record)
                native = r["buildProvenance"]["nativeInputs"]
                if mutation == "archive": native["archives"].pop(next(iter(native["archives"])))
                if mutation == "version": native["installedVersions"][next(iter(native["installedVersions"]))] = "changed"
                if mutation in ("vendor", "notice"):
                    group = c["vendor_payload" if mutation == "vendor" else "original_notice_payload"]
                    r["releaseInput"].pop(next(iter(group)))
                if mutation == "index": r["sourceInputs"]["win/notice-supplement/index.json"]["sha256"] = "0" * 64
                if mutation.startswith("extra-"): r["releaseInput"]["_internal/foreign." + mutation[6:]] = {"bytes": 1, "sha256": "0" * 64}
                if mutation == "audit": c["audit_checks"]["all_source_inputs_match"] = False
                if mutation == "release": c["source_release"] += "-foreign"
                if mutation == "application-source": r["sourceInputs"]["rednotebook/info.py"]["sha256"] = "0" * 64
                if mutation == "application-version": r["identity"]["version"] = "1.0.0.0"
                with self.assertRaises(ValueError): validate_native_closure(c, r)


if __name__ == "__main__":
    unittest.main()
