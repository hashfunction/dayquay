"""Replay the actual captured failure through native INPUT and product serialization."""
# Copyright 2026 Trieflow LLC. MIT.
import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'msix'),str(Path(__file__).resolve().parents[2])]
import installed_workflow_qualification as original
import capture_ui as capture
from rednotebook import storage
from rednotebook.data import Month

class NativeReplay:
    """Only the OS edge is replayed; _send/text/key construction are production."""
    foreground=101
    def __init__(self):self.batches=[];self.before_send=None;self.partial=False
    def IsWindow(self,_):return True
    def IsWindowVisible(self,_):return True
    def IsWindowEnabled(self,_):return True
    def GetForegroundWindow(self):return self.foreground
    def SendInput(self,count,inputs,size):
        partial=self.partial
        self.batches.append([(row.type,row.ki.wVk,row.ki.wScan,row.ki.dwFlags) for row in inputs])
        if self.before_send:self.before_send(self)
        return count-1 if partial else count
    def editor_text(self):
        result=[]
        for batch in self.batches:
            for kind,key,scan,flags in batch:
                if kind!=1 or flags & original._WindowsInput.KEYEVENTF_KEYUP:continue
                if flags & original._WindowsInput.KEYEVENTF_UNICODE:
                    # Exact recorded GTK behavior: LF Unicode packets disappeared.
                    if scan!=10:result.append(chr(scan))
                elif key==13:result.append('\n')
        return ''.join(result)


def native_ui(cls):
    ui=object.__new__(cls);ui.process_id=42;ui.main_hwnd=101;ui.current_title='Jotmorrow - Saturday, 9/12/2026'
    ui._input_hwnd=101;ui._input_title=ui.current_title;ui.user32=NativeReplay()
    ui._assert_process_live=lambda:None;ui._window_pid=lambda _:42;ui._title=lambda _:ui.current_title
    ui._main=mock.Mock();ui._click_editor=mock.Mock()
    return ui


def save_month(journal,text):
    month=Month(2026,9,{12:{'text':text}})
    storage._save_month_to_disk(month,str(journal))
    return (journal/'2026-09.txt').read_bytes()


class NewlineTests(unittest.TestCase):
    def setUp(self):
        self.cls=capture.ui_class(original,SimpleNamespace(),[],lambda _:None)
        self.text=capture.entry(datetime.date(2026,9,12))
        self.failure=json.loads((Path(__file__).with_name('fixtures')/'34684051917-input-failure.json').read_text())
    def test_recorded_failure_is_exactly_all_newlines_lost(self):
        diagnostic=self.failure['fictional_journal'];raw=diagnostic['fictional_saved_text'].encode()
        self.assertEqual(len(raw),diagnostic['bytes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),diagnostic['sha256'])
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();(root/'2026-09.txt').write_bytes(raw)
            loaded=storage.load_month_from_disk(root/'2026-09.txt',2026,9)
            self.assertEqual(loaded.get_day(12).text,self.text.replace('\n',''))
            self.assertEqual(self.text.count('\n'),23)
            with self.assertRaisesRegex(ValueError,'marker once'):
                original.capture_journal(root,capture.SENTINEL,(capture.MARKER,'#weekend #ideas #gratitude'))
    def test_old_native_route_reproduces_actual_yaml_bytes(self):
        ui=native_ui(original._WindowsInput)
        with mock.patch.object(original.time,'sleep'):ui.replace_editor_text(self.text)
        self.assertEqual(ui.user32.editor_text(),self.text.replace('\n',''))
        with tempfile.TemporaryDirectory() as t:
            actual=save_month(Path(t).resolve(),ui.user32.editor_text())
            self.assertEqual(actual,self.failure['fictional_journal']['fictional_saved_text'].encode())
    def test_capture_native_route_preserves_lines_and_real_serializer_oracles(self):
        ui=native_ui(self.cls)
        with mock.patch.object(original.time,'sleep'):ui.replace_editor_text(self.text)
        ui._main.assert_called_once_with();ui._click_editor.assert_called_once_with()
        self.assertEqual(ui.user32.editor_text(),self.text)
        self.assertFalse(any(scan==10 and flags & 4 for batch in ui.user32.batches for _,_,scan,flags in batch))
        self.assertEqual(sum(key==13 and flags==0 for batch in ui.user32.batches for _,key,_,flags in batch),23)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();save_month(root,ui.user32.editor_text())
            loaded=storage.load_month_from_disk(root/'2026-09.txt',2026,9)
            self.assertEqual(loaded.get_day(12).text,self.text)
            self.assertEqual(loaded.get_day(12).hashtags,['weekend','ideas','gratitude'])
            saved=original.capture_journal(root,capture.SENTINEL,(capture.MARKER,'#weekend #ideas #gratitude'))
            self.assertEqual(original.verify_protected_journal(root,capture.SENTINEL,capture.MARKER,saved)['files'],saved['files'])
    def test_newline_dispatch_retains_final_send_ownership_and_partial_failure(self):
        for mode in ('foreign','partial'):
            with self.subTest(mode=mode):
                ui=native_ui(self.cls)
                def change(edge):
                    # CTRL+A then first text line have reached the OS; next batch is Enter.
                    if len(edge.batches)==2:
                        if mode=='foreign':edge.foreground=999
                        else:edge.partial=True
                ui.user32.before_send=change
                with mock.patch.object(original.time,'sleep'),mock.patch.object(original.ctypes,'WinError',lambda _:OSError('partial native input'),create=True),mock.patch.object(original.ctypes,'get_last_error',lambda:5,create=True):
                    with self.assertRaises((ValueError,OSError)):ui.replace_editor_text('first\nsecond')
                self.assertEqual(len(ui.user32.batches),3 if mode=='partial' else 2)
                self.assertNotIn('second',ui.user32.editor_text())

if __name__=='__main__':unittest.main()
