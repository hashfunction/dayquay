"""Synthetic receipt mutations; native GUI success remains a Windows requirement."""
# Copyright 2026 Trieflow LLC. MIT.
import copy
import unittest

from source_publication import digest
from installed_workflow_qualification import restored_window_title
from store_workflow_evidence import validate_workflow


def workflow_fixture(title, helper_hash):
    journal = 'C:/Users/fixture/AppData/Roaming/DayQuay/data'
    marker, extra = digest(b'original text')['sha256'], digest(b'reopened text')['sha256']
    saved = dict(journal_root=journal, files={'2026-09.txt': digest(b'saved journal')},
                 sentinel_sha256=marker, additional_text_sha256=[])
    reopened = dict(saved, files={'2026-09.txt': digest(b'saved journal plus reopened text')},
                    additional_text_sha256=[extra])
    backup = dict(archive='D:/temp/.dayquay-install-' + 'a' * 32 + '/Jotmorrow-consumer-backup.zip',
                  archive_bytes=577, archive_sha256=digest(b'synthetic archive receipt')['sha256'],
                  manifest_verified=True, files=copy.deepcopy(reopened['files']))
    workflow = dict(schema_version=1, journal_backup_restore_workflow_tested=True,
                    input_method='owned Win32 SendInput keyboard/mouse', helper_sha256=helper_hash,
                    process_id=1616, main_window_handle=917834, saved=saved, reopened=reopened,
                    sentinel_sha256=marker, backup=backup, backup_after_restore=copy.deepcopy(backup),
                    reopen_transition=dict(away_title=restored_window_title(title, 'ReopenProbe'), return_title=title),
                    restored=dict(reopened, journal_root=journal[:-4] + 'RestoredQualification'),
                    restored_window_title=restored_window_title(title, 'RestoredQualification'),
                    original_after_restore=copy.deepcopy(reopened))
    stopped = dict(process_id=1616, wait_completed=True, normal_exit=True, exit_code=0, observation_error=None)
    installed = dict(window=dict(process_id=1616, main_window_handle=917834), process_exit=stopped,
                     cleanup_process_exit=copy.deepcopy(stopped), installed_consumer_workflow=copy.deepcopy(workflow))
    return workflow, installed


class StoreWorkflowEvidenceTests(unittest.TestCase):
    title = 'Jotmorrow - Saturday, 9/12/2026'
    helper_hash = 'a' * 64

    def test_complete_receipt_preserves_reopened_original_and_backup(self):
        workflow, installed = workflow_fixture(self.title, self.helper_hash)
        validate_workflow(workflow, installed, self.title, self.helper_hash)

    def test_receipt_substitution_and_loss_of_each_independent_fact_rejected(self):
        mutations = {
            'wrong-helper': lambda w, i: w.update(helper_sha256='b' * 64),
            'no-input-proof': lambda w, i: w.update(input_method='fixture'),
            'wrong-pid': lambda w, i: w.update(process_id=17),
            'wrong-hwnd': lambda w, i: w.update(main_window_handle=17),
            'boolean-pid': lambda w, i: w.update(process_id=True),
            'killed-process': lambda w, i: i['process_exit'].update(exit_code=1, normal_exit=False),
            'cleanup-unobserved': lambda w, i: i['cleanup_process_exit'].update(observation_error='exited before observation'),
            'wrong-original': lambda w, i: w['saved'].update(sentinel_sha256='b' * 64),
            'extra-original-file': lambda w, i: w['saved']['files'].update({'foreign.txt': digest(b'foreign')}),
            'missing-saved-bytes': lambda w, i: w['saved']['files']['2026-09.txt'].update(bytes=0),
            'reopen-without-edit': lambda w, i: w.update(reopened=copy.deepcopy(w['saved'])),
            'reopen-no-marker': lambda w, i: w['reopened'].update(additional_text_sha256=[]),
            'reopen-wrong-folder': lambda w, i: w['reopen_transition'].update(away_title='foreign'),
            'original-overwritten': lambda w, i: w['original_after_restore']['files']['2026-09.txt'].update(sha256='0' * 64),
            'foreign-restored-folder': lambda w, i: w['restored'].update(journal_root='C:/foreign'),
            'foreign-original-folder': lambda w, i: w['original_after_restore'].update(journal_root='C:/foreign'),
            'relative-backup': lambda w, i: w['backup'].update(archive='relative/backup.zip'),
            'foreign-backup-owner': lambda w, i: w['backup'].update(archive='C:/foreign/Jotmorrow-consumer-backup.zip'),
            'backup-unverified': lambda w, i: w['backup'].update(manifest_verified=False),
            'backup-replaced': lambda w, i: w['backup_after_restore'].update(archive_sha256='0' * 64),
            'missing-field': lambda w, i: w.pop('restored'),
            'embedded-disagrees': lambda w, i: i['installed_consumer_workflow'].update(process_id=99),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                w, i = workflow_fixture(self.title, self.helper_hash)
                # Except this explicit disagreement, coherently replace the final
                # embedded copy so independent semantic checks have to reject it.
                mutate(w, i)
                if name != 'embedded-disagrees': i['installed_consumer_workflow'] = copy.deepcopy(w)
                with self.assertRaises(ValueError): validate_workflow(w, i, self.title, self.helper_hash)


if __name__ == '__main__':
    unittest.main()
