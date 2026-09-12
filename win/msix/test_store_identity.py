"""Exercise both fixed package identities with real stage/ZIP/XML boundaries."""
# Copyright 2026 Trieflow LLC. MIT.
import unittest
import zipfile

import msix_qualification as msix
import test_msix_qualification as fixtures


class StoreIdentityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.QualificationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_store_stage_container_and_installed_tree_require_exact_mode(self):
        f = self.fixture
        stage = f.root / "store-stage"
        record = msix.stage_release(f.release, f.artwork, stage, f.commit,
                                    f.inventory, f.startup, f.source, "store")
        self.assertEqual(record["identity"], msix.STORE_IDENTITY)
        self.assertEqual(record["identity"]["packageName"], "1659hashfunction.DayQuay")
        self.assertEqual(record["identity"]["publisher"], "CN=B6A2631A-FD32-45CC-AE12-82466975F528")
        self.assertEqual(record["identity"]["applicationId"], "DayQuay")
        self.assertEqual(record["identity"]["executable"], "Jotmorrow.exe")
        self.assertEqual(record["identity"]["version"], "1.0.1.0")
        self.assertIn(b'Jotmorrow', (stage / 'AppxManifest.xml').read_bytes())
        self.assertIn("Jotmorrow.exe", record["payload"])
        self.assertNotIn("DayQuay.exe", record["payload"])
        self.assertEqual(record["identityMode"], "store")
        self.assertIs(record["qualificationIdentityOnly"], False)
        self.assertIs(record["storeIdentityUsed"], True)
        package = f.root / "store.msix"
        with zipfile.ZipFile(package, "w") as archive:
            for relative in record["payload"]:
                archive.write(stage / relative, relative)
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("AppxBlockMap.xml", "<BlockMap/>")
        self.assertEqual(msix.verify_msix(package, record["payload"], "store")["verifiedPayloadFiles"], len(record["payload"]))
        msix.verify_unpacked(stage, record["payload"], "store")
        msix.verify_installed(stage, record["payload"], "store")
        for verify, target in ((msix.verify_msix, package), (msix.verify_unpacked, stage), (msix.verify_installed, stage)):
            with self.assertRaises(ValueError):
                verify(target, record["payload"], "qualification")

    def test_fixed_store_manifest_rejects_coherent_identity_or_presentation_changes(self):
        data = msix.create_manifest("store")
        self.assertEqual(msix.validate_manifest(data, "store"), msix.STORE_IDENTITY)
        for before, after in ((b"1659hashfunction.DayQuay", b"1659hashfunction.Foreign"),
                              (b"CN=B6A2631A-FD32-45CC-AE12-82466975F528", b"CN=Foreign"),
                              (b"hashfunction", b"AnotherPublisher"),
                              (b"runFullTrust", b"broadFileSystemAccess")):
            with self.subTest(before=before), self.assertRaises(ValueError):
                msix.validate_manifest(data.replace(before, after), "store")
        with self.assertRaises(ValueError):
            msix.create_manifest("arbitrary")


if __name__ == "__main__":
    unittest.main()
