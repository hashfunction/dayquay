"""Capture-only sequence fixtures; actual screenshots still require Windows."""
import datetime
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import sys
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'msix'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from rednotebook.data import Month
from rednotebook import storage

def save_real_month(journal,text):
    month=Month(2026,9,{12:{'text':text}})
    storage._save_month_to_disk(month,str(journal))

import installed_workflow_qualification as original
try:
    import capture_ui as capture
except ImportError:
    capture=None


class CaptureUITests(unittest.TestCase):
    def test_original_entry_is_dated_and_real_hashtags_are_recognized(self):
        self.assertIsNotNone(capture)
        text=capture.entry(datetime.date(2026,9,12))
        self.assertIn('12 September 2026',text)
        self.assertLess(len(text),1800)
        import importlib.util
        path=Path(__file__).resolve().parents[2]/'rednotebook/data.py'
        spec=importlib.util.spec_from_file_location('original_data',path);data=importlib.util.module_from_spec(spec);spec.loader.exec_module(data)
        self.assertEqual([row[2] for row in data.HASHTAG.findall(text)],['weekend','ideas','gratitude'])
        self.assertNotIn('QUALIFICATION',text)

    def test_real_file_oracles_guard_capture_sequence(self):
        self.assertIsNotNone(capture)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();journal=root/'data';journal.mkdir();archive=root/'Autumn-journal.zip';calls=[]
            class UI:
                current_title='Jotmorrow - Saturday, 9/12/2026'
                def replace_editor_text(self,text):
                    self.month=Month(2026,9,{12:{'text':text}});self.month.edited=True;self.save_results=[];calls.append('type')
                def save(self):
                    self.save_results.append(storage.save_months_to_disk({'2026-09':self.month},str(journal)));calls.append('save')
                def show_top(self):calls.append('show-top')
                def capture(self,name):calls.append(name)
                def create_backup(self,path):
                    calls.append('backup');data=(journal/'2026-09.txt').read_bytes()
                    with zipfile.ZipFile(path,'w') as z:
                        z.writestr('2026-09.txt',data);z.writestr(original.MANIFEST_NAME,json.dumps(dict(created_at='2026-09-12',format='dayquay-backup',version=1,
                            entries=[dict(path='2026-09.txt',size=len(data),sha256=original._sha256(data))])))
                def restore_backup(self,path,parent,name,title):
                    calls.append('02-restore-preview');out=parent/name;out.mkdir()
                    with zipfile.ZipFile(path) as z:(out/'2026-09.txt').write_bytes(z.read('2026-09.txt'))
                    self.current_title=title;calls.append('restore')
            ui=UI();result=capture.run_capture(ui,original,journal,archive,root,'RestoredJournal',datetime.date(2026,9,12))
            self.assertEqual(ui.save_results,[True,False])
            self.assertEqual(calls,['type','save','save','show-top','01-journal-entry','backup','02-restore-preview','restore','show-top','03-restored-journal'])
            self.assertEqual(result['saved']['files'],result['restored']['files'])
            self.assertEqual(result['backup'],result['backup_after_restore'])
            self.assertFalse(result['consumer_acceptance'])

    def test_status_save_follows_persisted_proof_and_cannot_change_journal(self):
        for changed in (False,True):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as t:
                root=Path(t).resolve();journal=root/'data';journal.mkdir();calls=[]
                class UI:
                    current_title='Jotmorrow - Saturday, 9/12/2026'
                    def replace_editor_text(self,text):
                        self.month=Month(2026,9,{12:{'text':text}});self.month.edited=True
                    def save(self):
                        calls.append('save')
                        if calls.count('save')==2:
                            if 'persisted' not in calls:raise AssertionError('Second Save preceded persisted-byte proof')
                            if changed:(journal/'2026-09.txt').write_text('unexpected changed bytes')
                        storage.save_months_to_disk({'2026-09':self.month},str(journal))
                    def show_top(self):calls.append('show-top')
                    def capture(self,name):calls.append('capture');raise RuntimeError('first image reached')
                real_capture=original.capture_journal
                def proof(*args,**kwargs):
                    result=real_capture(*args,**kwargs);calls.append('persisted');return result
                with mock.patch.object(original,'capture_journal',side_effect=proof):
                    if changed:
                        with self.assertRaises(ValueError):capture.run_capture(UI(),original,journal,root/'a.zip',root,'RestoredJournal',datetime.date(2026,9,12))
                        self.assertEqual(calls,['save','persisted','save'])
                    else:
                        with self.assertRaisesRegex(RuntimeError,'first image reached'):
                            capture.run_capture(UI(),original,journal,root/'a.zip',root,'RestoredJournal',datetime.date(2026,9,12))
                        self.assertEqual(calls,['save','persisted','save','persisted','show-top','capture'])

    def test_backup_failure_does_not_reach_restore_or_later_screens(self):
        self.assertIsNotNone(capture)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();journal=root/'data';journal.mkdir();calls=[]
            class UI:
                current_title='Jotmorrow - Saturday, 9/12/2026'
                def replace_editor_text(self,text):save_real_month(journal,text)
                def save(self):pass
                def show_top(self):pass
                def capture(self,name):calls.append(name)
                def create_backup(self,path):raise ValueError('real backup failed')
                def restore_backup(self,*args):self.fail('restore must not run')
            with self.assertRaisesRegex(ValueError,'real backup failed'):
                capture.run_capture(UI(),original,journal,root/'a.zip',root,'RestoredJournal',datetime.date(2026,9,12))
            self.assertEqual(calls,['01-journal-entry'])

    def test_actual_modal_hook_captures_before_confirmation_and_refuses_repeat(self):
        calls=[];captured=[]
        class Base:
            VK={'CTRL':0x11}
            current_title='Jotmorrow - Saturday, 9/12/2026';main_hwnd=10;process_id=42
            def _wait_window(self,title,present=True,timeout=12):calls.append('observe:'+title);return 20
            def _assert_process_live(self):calls.append('live')
            def _foreground(self,hwnd,title):calls.append(('foreground',hwnd,title))
            def _main(self):calls.append('main')
            def chord(self,*keys):calls.append(keys)
        args=SimpleNamespace(powershell='pwsh',record=Path('record.json'),output=Path('output'))
        UI=capture.ui_class(SimpleNamespace(_WindowsInput=Base),args,captured,lambda command:calls.append(command))
        ui=UI();ui.show_top();self.assertEqual(UI.VK['HOME'],0x24)
        self.assertEqual(calls[:2],['main',('CTRL','HOME')])
        self.assertEqual(ui._wait_window('Restore portable backup'),20)
        self.assertEqual(captured,['02-restore-preview'])
        frame=calls[-1];self.assertEqual(frame[frame.index('-TargetWindowHandle')+1],'20')
        self.assertEqual(frame[frame.index('-MainWindowHandle')+1],'10')
        with self.assertRaisesRegex(ValueError,'repeated'):ui._wait_window('Restore portable backup')
        ui._wait_window('Restore portable backup',present=False)
        self.assertEqual(captured,['02-restore-preview'])



if __name__=='__main__':unittest.main()
