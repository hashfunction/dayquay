import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import capture_checks as checks


class CaptureChecksTests(unittest.TestCase):
    def fixture(self):
        rows=json.loads((Path(__file__).with_name('fixtures')/'original-receipts.json').read_text())
        run={'id':int(checks.RUN),'head_sha':checks.SOURCE,'run_attempt':1,'conclusion':'success',
            'repository':{'full_name':'hashfunction/dayquay'},'path':'.github/workflows/build-windows.yml'}
        return rows['ready'],rows['installed'],run

    def test_actual_original_receipt_shape_passes(self):
        checks.assert_current_capture_binding();checks.validate_receipts(*self.fixture())
        with patch.object(checks.msix,'STORE_IDENTITY',{}),self.assertRaises(ValueError):checks.assert_current_capture_binding()

    def test_source_run_bytes_and_incomplete_lifecycles_refuse(self):
        changes=[(0,'source_commit','a'*40),(0,'unsigned_store_package_ready',1),(0,'identity',{}),(0,'reviewed_public_source','a'*40),
            (0,'unsigned_package',{}),(1,'journal_backup_restore_workflow_tested',False),(1,'workflow_profile_removed',False),
            (1,'uninstall_verified',False),(1,'clean_close_verified',False),(1,'unsigned_package_sha256','1'*64),
            (1,'cleanup_errors',['failure']),(1,'residual_package_full_names',['foreign']),(1,'certificate_private_key_exported',True),
            (2,'conclusion','failure'),(2,'run_attempt',True),(2,'run_attempt',2),(2,'head_sha','a'*40)]
        for index,key,value in changes:
            rows=copy.deepcopy(self.fixture());rows[index][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):checks.validate_receipts(*rows)

    def test_actual_metadata_and_source_evidence_hashes_are_checked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);metadata=root/'metadata';metadata.mkdir();source=root/'source';source.mkdir()
            path=metadata/'receipt.json';path.write_text('{}')
            ready={'evidence':{'build-evidence/receipt.json':checks.digest(path)}}
            checks.verify_evidence(ready,metadata,source)
            path.write_text('{ }')
            with self.assertRaises(ValueError):checks.verify_evidence(ready,metadata,source)
            for bad in ('../outside','build-evidence/../../outside','C:/other','a\\b','/absolute'):
                with self.subTest(bad=bad),self.assertRaises(ValueError):checks.verify_evidence({'evidence':{bad:{}}},metadata,source)

    def test_qualified_checkout_must_be_exact_and_clean(self):
        with patch('subprocess.check_output',side_effect=[checks.SOURCE+'\n','']):checks.assert_qualified_checkout(Path('.'))
        for values in [('a'*40+'\n',''),(checks.SOURCE+'\n',' M original.py\n')]:
            with patch('subprocess.check_output',side_effect=values),self.assertRaises(ValueError):checks.assert_qualified_checkout(Path('.'))


if __name__=='__main__':unittest.main()
