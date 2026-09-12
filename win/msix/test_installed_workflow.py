"""Installed consumer journal/backup/restore qualification tests."""

import ast
import hashlib
import json
from ctypes import wintypes
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zipfile

import installed_workflow_qualification as workflow


SENTINEL = "DAYQUAY-INSTALLED-WORKFLOW-7F4C9A2E"
REOPEN_MARKER = "DAYQUAY-REOPENED-WORKFLOW-1D8B6C3F"
MONTH_BYTES = b"11:\n  text: DAYQUAY-INSTALLED-WORKFLOW-7F4C9A2E\n"
REOPENED_BYTES = (
    b"11:\n  text: DAYQUAY-INSTALLED-WORKFLOW-7F4C9A2E\\n"
    b"DAYQUAY-REOPENED-WORKFLOW-1D8B6C3F\n"
)


def write_backup(path, relative, content):
    record = {
        "path": relative,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }
    manifest = {
        "created_at": "2026-09-11T22:00:00+00:00",
        "entries": [record],
        "format": "dayquay-backup",
        "version": 1,
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(relative, content)
        archive.writestr(
            "dayquay-manifest.json",
            json.dumps(manifest, separators=(",", ":")).encode("utf-8"),
        )


class FakeConsumerUi:
    def __init__(self, journal, archive, restored):
        self.journal = journal
        self.archive = archive
        self.restored = restored
        self.calls = []
        self.content = MONTH_BYTES

    def replace_editor_text(self, text):
        self.calls.append(("replace_editor_text", text))

    def save(self):
        self.calls.append(("save",))
        (self.journal / "2026-09.txt").write_bytes(self.content)

    def reopen_journal(self, path, transition_path, transition_title, return_title):
        self.calls.append(
            ("reopen_journal", path, transition_path, transition_title, return_title)
        )
        return {"away_title": transition_title, "return_title": return_title}

    def append_editor_text(self, text):
        self.calls.append(("append_editor_text", text))
        self.content = REOPENED_BYTES

    def create_backup(self, path):
        self.calls.append(("create_backup", path))
        write_backup(path, "2026-09.txt", self.content)

    def restore_backup(self, archive, parent, name, expected_title):
        self.calls.append(("restore_backup", archive, parent, name, expected_title))
        self.restored.mkdir()
        shutil.copyfile(self.journal / "2026-09.txt", self.restored / "2026-09.txt")


class InstalledWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dayquay-installed-workflow-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.profile = self.root / "DayQuay"
        self.journal = self.profile / "data"
        self.journal.mkdir(parents=True)
        self.archive = self.root / "consumer-backup.zip"
        self.restored = self.profile / "RestoredQualification"
        self.reopen_probe = self.profile / "ReopenProbe"
        self.reopen_probe.mkdir()

    def run_workflow(self, ui, immediate=False):
        arguments = {
            "ui": ui,
            "journal": self.journal,
            "archive": self.archive,
            "restore_parent": self.profile,
            "restore_name": self.restored.name,
            "sentinel": SENTINEL,
            "reopen_marker": REOPEN_MARKER,
            "initial_title": "DayQuay - Friday, 9/11/2026",
        }
        if not immediate:
            return workflow.run_consumer_workflow(**arguments)
        with mock.patch.object(
            workflow, "_eventually", side_effect=lambda operation, _label: operation()
        ):
            return workflow.run_consumer_workflow(**arguments)

    def test_consumer_sequence_verifies_saved_reopened_backup_and_restored_bytes(self):
        ui = FakeConsumerUi(self.journal, self.archive, self.restored)

        evidence = self.run_workflow(ui)

        self.assertEqual(
            [call[0] for call in ui.calls],
            [
                "replace_editor_text",
                "save",
                "reopen_journal",
                "append_editor_text",
                "save",
                "create_backup",
                "restore_backup",
            ],
        )
        self.assertTrue(evidence["journal_backup_restore_workflow_tested"])
        self.assertEqual(evidence["input_method"], "owned Win32 SendInput keyboard/mouse")
        self.assertNotEqual(evidence["saved"]["files"], evidence["reopened"]["files"])
        self.assertEqual(evidence["reopened"]["files"], evidence["backup"]["files"])
        self.assertEqual(evidence["reopened"]["files"], evidence["restored"]["files"])
        self.assertEqual(
            evidence["reopened"]["files"], evidence["original_after_restore"]["files"]
        )
        self.assertEqual(
            evidence["backup"]["archive_sha256"],
            evidence["backup_after_restore"]["archive_sha256"],
        )
        self.assertEqual(
            evidence["reopen_transition"],
            {
                "away_title": "DayQuay - ReopenProbe - Friday, 9/11/2026",
                "return_title": "DayQuay - Friday, 9/11/2026",
            },
        )
        self.assertEqual(
            evidence["restored_window_title"],
            "DayQuay - RestoredQualification - Friday, 9/11/2026",
        )

    def test_noop_reopen_cannot_qualify(self):
        class NoopReopenUi(FakeConsumerUi):
            def reopen_journal(self, *_args):
                self.calls.append(("reopen_journal",))
                return None

        with self.assertRaisesRegex(ValueError, "observable journal transition"):
            self.run_workflow(NoopReopenUi(self.journal, self.archive, self.restored))

    def test_restore_deleting_original_journal_is_rejected(self):
        class DeleteOriginalUi(FakeConsumerUi):
            def restore_backup(self, *args):
                super().restore_backup(*args)
                (self.journal / "2026-09.txt").unlink()

        with self.assertRaisesRegex(ValueError, "original journal after restore"):
            self.run_workflow(
                DeleteOriginalUi(self.journal, self.archive, self.restored), immediate=True
            )

    def test_restore_changing_or_adding_original_journal_files_is_rejected(self):
        for mutation in ("change", "extra"):
            with self.subTest(mutation=mutation):
                with tempfile.TemporaryDirectory(
                    prefix="dayquay-source-mutation-"
                ) as temporary:
                    root = Path(temporary)
                    profile = root / "DayQuay"
                    journal = profile / "data"
                    journal.mkdir(parents=True)
                    (profile / "ReopenProbe").mkdir()
                    archive = root / "backup.zip"
                    restored = profile / "RestoredQualification"

                    class MutateOriginalUi(FakeConsumerUi):
                        def restore_backup(self, *args):
                            super().restore_backup(*args)
                            if mutation == "change":
                                (self.journal / "2026-09.txt").write_bytes(b"changed")
                            else:
                                (self.journal / "unexpected.txt").write_bytes(b"foreign")

                    with mock.patch.object(
                        workflow,
                        "_eventually",
                        side_effect=lambda operation, _label: operation(),
                    ), self.assertRaisesRegex(ValueError, "original journal after restore"):
                        workflow.run_consumer_workflow(
                            ui=MutateOriginalUi(journal, archive, restored),
                            journal=journal,
                            archive=archive,
                            restore_parent=profile,
                            restore_name=restored.name,
                            sentinel=SENTINEL,
                            reopen_marker=REOPEN_MARKER,
                            initial_title="DayQuay - Friday, 9/11/2026",
                        )

    def test_restore_changing_backup_archive_is_rejected(self):
        class ChangeArchiveUi(FakeConsumerUi):
            def restore_backup(self, *args):
                super().restore_backup(*args)
                with self.archive.open("ab") as stream:
                    stream.write(b"changed after restore")

        with self.assertRaisesRegex(ValueError, "backup after restore"):
            self.run_workflow(
                ChangeArchiveUi(self.journal, self.archive, self.restored), immediate=True
            )

    def test_tampered_archive_and_restored_extra_file_are_rejected(self):
        month = self.journal / "2026-09.txt"
        month.write_bytes(MONTH_BYTES)
        saved = workflow.capture_journal(self.journal, SENTINEL)
        write_backup(self.archive, month.name, MONTH_BYTES + b"changed")
        with self.assertRaisesRegex(ValueError, "backup.*saved journal"):
            workflow.verify_backup(self.archive, saved)

        self.restored.mkdir()
        (self.restored / month.name).write_bytes(MONTH_BYTES)
        (self.restored / "extra.txt").write_bytes(b"foreign")
        with self.assertRaisesRegex(ValueError, "restored journal"):
            workflow.verify_restored(self.restored, SENTINEL, REOPEN_MARKER, saved)

    def test_saved_journal_requires_exactly_one_month_and_exact_sentinel(self):
        with self.assertRaisesRegex(ValueError, "month"):
            workflow.capture_journal(self.journal, SENTINEL)
        (self.journal / "2026-09.txt").write_bytes(b"11:\n  text: something else\n")
        with self.assertRaisesRegex(ValueError, "qualification marker"):
            workflow.capture_journal(self.journal, SENTINEL)
        (self.journal / "extra.txt").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            workflow.capture_journal(self.journal, SENTINEL)

    def test_restored_title_rejects_non_default_initial_contract(self):
        self.assertEqual(
            workflow.restored_window_title(
                "DayQuay - Friday, 9/11/2026", "RestoredQualification"
            ),
            "DayQuay - RestoredQualification - Friday, 9/11/2026",
        )
        for title in ("DayQuay", "Other - Friday, 9/11/2026", "DayQuay - named - date"):
            with self.subTest(title=title):
                with self.assertRaisesRegex(ValueError, "default journal title"):
                    workflow.restored_window_title(title, "RestoredQualification")

    def test_journal_directory_discovery_matches_native_chooser_title(self):
        source_root = Path(__file__).resolve().parents[2]
        glade = ET.parse(source_root / "rednotebook/files/main_window.glade")
        chooser = glade.find(".//object[@id='dir_chooser']")
        self.assertIsNotNone(chooser)
        title = chooser.find("./property[@name='title']")
        self.assertIsNotNone(title)
        self.assertEqual(workflow.JOURNAL_DIRECTORY_CHOOSER_TITLE, title.text)

        module = ast.parse(
            (source_root / "rednotebook/gui/main_window.py").read_text(encoding="utf-8")
        )
        implementation = next(
            node
            for node in ast.walk(module)
            if isinstance(node, ast.FunctionDef) and node.name == "get_new_journal_dir"
        )
        self.assertFalse(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "set_title"
                for node in ast.walk(implementation)
            ),
            "runtime code now overrides the static chooser title",
        )

    def test_reopen_targets_exact_native_directory_chooser(self):
        native = object.__new__(workflow._WindowsInput)
        native.current_title = "DayQuay - Friday, 9/11/2026"
        native.main_hwnd = 101
        native._main = mock.Mock()
        native.chord = mock.Mock()
        native._select_path = mock.Mock()
        native._wait_window = mock.Mock()
        native._assert_owned = mock.Mock()
        original = Path("C:/owned/data")
        transition = Path("C:/owned/ReopenProbe")

        evidence = native.reopen_journal(
            original,
            transition,
            "DayQuay - ReopenProbe - Friday, 9/11/2026",
            "DayQuay - Friday, 9/11/2026",
        )

        self.assertEqual(
            native._select_path.call_args_list,
            [
                mock.call(workflow.JOURNAL_DIRECTORY_CHOOSER_TITLE, transition, "O"),
                mock.call(workflow.JOURNAL_DIRECTORY_CHOOSER_TITLE, original, "O"),
            ],
        )
        self.assertEqual(
            evidence,
            {
                "away_title": "DayQuay - ReopenProbe - Friday, 9/11/2026",
                "return_title": "DayQuay - Friday, 9/11/2026",
            },
        )

    def test_named_and_letter_keys_encode_without_evaluating_the_wrong_fallback(self):
        native = object.__new__(workflow._WindowsInput)

        self.assertEqual(native._key("CTRL").ki.wVk, 0x11)
        self.assertEqual(native._key("B").ki.wVk, ord("B"))

    def test_timeout_records_whether_the_named_window_should_be_absent(self):
        native = object.__new__(workflow._WindowsInput)
        native._owned_windows = lambda: [(17, "Select a directory")]
        with self.assertRaisesRegex(ValueError, "present=False"):
            native._wait_window("Select a directory", present=False, timeout=0)
        self.assertEqual(native._wait_condition["present"], False)
        self.assertEqual(native._wait_condition["title"], "Select a directory")
        self.assertEqual(native._wait_condition["status"], "timed_out")

    def test_path_selection_failure_retains_steps_without_extra_inputs(self):
        native = object.__new__(workflow._WindowsInput)
        native._observe_diagnostic_state = lambda: {"focus": {"hwnd": 17}}
        native._wait_window = mock.Mock(side_effect=[17, ValueError("chooser stayed open")])
        native._foreground = mock.Mock()
        native._owned_windows = lambda: [(17, "Select a directory")]
        native.chord = mock.Mock()
        native.text = mock.Mock()
        native.press = mock.Mock()
        with mock.patch.object(workflow.time, "sleep"):
            with self.assertRaisesRegex(ValueError, "chooser stayed open"):
                native._select_path("Select a directory", self.reopen_probe, "O")
        self.assertEqual(native.chord.call_args_list, [mock.call("CTRL", "L"), mock.call("ALT", "O")])
        native.text.assert_called_once_with(str(self.reopen_probe).replace("/", "\\"))
        native.press.assert_called_once_with("ENTER")
        self.assertEqual(native._path_selection["path"], str(self.reopen_probe))
        self.assertTrue(native._path_selection["is_directory"])
        self.assertEqual([row["step"] for row in native._diagnostic_trace], [
            "dialog_foreground", "after_ctrl_l", "after_path_text", "after_enter", "after_accept_key",
        ])
        self.assertEqual(native._diagnostic_trace[-1]["state"]["focus"]["hwnd"], 17)

    def test_chooser_input_uses_windows_separators_with_real_action_order(self):
        for supplied, expected in (
            ("D:/a/_temp/DayQuay/ReopenProbe", r"D:\a\_temp\DayQuay\ReopenProbe"),
            (r"C:\Users/runneradmin/DayQuay/data", r"C:\Users\runneradmin\DayQuay\data"),
            ("C:/Journals/Café, notes/backup.zip", "C:\\Journals\\Café, notes\\backup.zip"),
            ("//server/share/DayQuay/data", r"\\server\share\DayQuay\data"),
            (r"C:\DayQuay\data", r"C:\DayQuay\data"),
        ):
            with self.subTest(supplied=supplied):
                native = object.__new__(workflow._WindowsInput)
                calls = mock.Mock()
                native._wait_window = calls.wait_window
                calls.wait_window.side_effect = [17, None]
                native._foreground = calls.foreground
                native._owned_windows = lambda: []
                native._observe_diagnostic_state = lambda: {}
                native.chord, native.text, native.press = calls.chord, calls.text, calls.press
                with mock.patch.object(workflow.time, "sleep"):
                    native._select_path("Select a directory", supplied, "O")
                self.assertEqual(calls.mock_calls, [
                    mock.call.wait_window("Select a directory"),
                    mock.call.foreground(17, "Select a directory"),
                    mock.call.chord("CTRL", "L"),
                    mock.call.text(expected),
                    mock.call.press("ENTER"),
                    mock.call.wait_window("Select a directory", present=False),
                ])
                self.assertEqual(native._path_selection["path"], supplied)
                self.assertEqual(native._path_selection["input_text"], expected)

    def test_chooser_foreground_refusal_prevents_path_and_key_input(self):
        native = object.__new__(workflow._WindowsInput)
        native._wait_window = mock.Mock(return_value=17)
        native._foreground = mock.Mock(side_effect=ValueError("ownership changed"))
        native.chord, native.text, native.press = mock.Mock(), mock.Mock(), mock.Mock()
        with self.assertRaisesRegex(ValueError, "ownership"):
            native._select_path("Select a directory", "C:/DayQuay/data", "O")
        native.chord.assert_not_called()
        native.text.assert_not_called()
        native.press.assert_not_called()

    def test_general_journal_text_preserves_slashes_and_unicode_input_units(self):
        native = object.__new__(workflow._WindowsInput)
        sent = []
        native._send = sent.extend
        text = "Journal/entry — café 💡"
        native.text(text)
        encoded = b"".join(key.ki.wScan.to_bytes(2, "little") for key in sent[::2])
        self.assertEqual(encoded.decode("utf-16-le"), text)
        self.assertEqual(len(sent), len(text.encode("utf-16-le")))
        for down, up in zip(sent[::2], sent[1::2]):
            self.assertEqual(down.ki.wScan, up.ki.wScan)
            self.assertEqual(down.ki.dwFlags, native.KEYEVENTF_UNICODE)
            self.assertEqual(up.ki.dwFlags, native.KEYEVENTF_UNICODE | native.KEYEVENTF_KEYUP)

    def test_diagnostic_observation_failure_does_not_inject_or_interrupt_input(self):
        native = object.__new__(workflow._WindowsInput)
        native._observe_diagnostic_state = mock.Mock(side_effect=OSError("focus unavailable"))
        native._wait_window = mock.Mock(side_effect=[17, None])
        native._foreground = mock.Mock()
        native._owned_windows = lambda: []
        native.chord = mock.Mock()
        native.text = mock.Mock()
        native.press = mock.Mock()
        with mock.patch.object(workflow.time, "sleep"):
            native._select_path("Select a directory", self.reopen_probe, "O")
        native.chord.assert_called_once_with("CTRL", "L")
        native.text.assert_called_once_with(str(self.reopen_probe).replace("/", "\\"))
        native.press.assert_called_once_with("ENTER")
        self.assertEqual(native._diagnostic_trace[-1]["state"], {"observation_error": "focus unavailable"})

    def test_diagnostics_never_read_foreign_window_text(self):
        native = object.__new__(workflow._WindowsInput)
        native.process_id = 7
        native.user32 = mock.Mock()
        native.user32.IsWindow.return_value = True
        native._window_pid = lambda _hwnd: 999
        native._title = mock.Mock(side_effect=AssertionError("foreign title read"))
        self.assertEqual(native._diagnostic_window(17), {"hwnd": 17, "live": True, "owned": False})
        native._title.assert_not_called()
        native.user32.GetClassNameW.assert_not_called()

    def test_cli_failure_writes_diagnostics_and_never_a_success_receipt(self):
        output = self.root / "installed-consumer-workflow.json"
        ui = mock.Mock()
        ui.failure_diagnostics.return_value = {
            "wait_condition": {"title": "Select a directory", "present": False},
            "path_selection": {"path": str(self.reopen_probe)},
        }
        arguments = [
            "workflow", "--process-id", "7", "--main-window-handle", "17",
            "--initial-title", "DayQuay - Friday, 9/11/2026",
            "--profile-root", str(self.profile), "--archive", str(self.archive),
            "--restore-name", "RestoredQualification", "--sentinel", SENTINEL,
            "--reopen-marker", REOPEN_MARKER, "--output", str(output),
        ]
        with mock.patch.object(sys, "argv", arguments), mock.patch.object(
            workflow, "_WindowsInput", return_value=ui
        ), mock.patch.object(workflow, "run_consumer_workflow", side_effect=ValueError("chooser stayed open")):
            with self.assertRaises(SystemExit) as failure:
                workflow.main()
        self.assertEqual(failure.exception.code, 2)
        self.assertFalse(output.exists())
        record = json.loads(output.with_name("installed-consumer-workflow-failure.json").read_text())
        self.assertFalse(record["workflow_qualified"])
        self.assertEqual(record["error"], "chooser stayed open")
        self.assertEqual(record["process_id"], 7)
        self.assertFalse(record["diagnostics"]["wait_condition"]["present"])
        ui.close.assert_called_once()

    def test_user32_pointer_and_handle_signatures_are_explicit(self):
        class Function:
            pass

        class User32:
            pass

        user32 = User32()
        for name in (
            "EnumWindows",
            "GetForegroundWindow",
            "GetWindowRect",
            "GetWindowTextLengthW",
            "GetWindowTextW",
            "GetClassNameW",
            "GetGUIThreadInfo",
            "GetWindowThreadProcessId",
            "IsWindow",
            "IsWindowEnabled",
            "IsWindowVisible",
            "SendInput",
            "SetCursorPos",
            "SetForegroundWindow",
            "ShowWindow",
        ):
            setattr(user32, name, Function())
        native = object.__new__(workflow._WindowsInput)
        native.user32 = user32

        native._configure_user32()

        self.assertIs(user32.GetForegroundWindow.restype, wintypes.HWND)
        self.assertEqual(user32.GetWindowRect.argtypes[0], wintypes.HWND)
        self.assertEqual(user32.GetWindowThreadProcessId.argtypes[0], wintypes.HWND)
        self.assertEqual(user32.EnumWindows.argtypes[0], native._enum_callback_type)
        self.assertEqual(user32.SendInput.restype, wintypes.UINT)
        self.assertEqual(user32.GetGUIThreadInfo.argtypes[1], workflow.ctypes.POINTER(native.GUITHREADINFO))

    def test_each_input_packet_rechecks_exact_owned_foreground_target(self):
        class User32:
            def __init__(self):
                self.foreground = 100
                self.live = True
                self.enabled = True
                self.sends = 0

            def IsWindow(self, _hwnd):
                return self.live

            def IsWindowVisible(self, _hwnd):
                return self.live

            def IsWindowEnabled(self, _hwnd):
                return self.enabled

            def GetForegroundWindow(self):
                return self.foreground

            def SendInput(self, count, _inputs, _size):
                self.sends += 1
                return count

        def new_native():
            native = object.__new__(workflow._WindowsInput)
            native.process_id = 7
            native.user32 = User32()
            native._input_hwnd = 100
            native._input_title = "Expected dialog"
            native._window_pid = lambda _hwnd: 7
            native._title = lambda hwnd: (
                "Expected dialog" if int(hwnd) == 100 else "Unexpected dialog"
            )
            native._assert_process_live = lambda: None
            return native

        valid = new_native()
        valid._send([valid._key("ENTER")])
        self.assertEqual(valid.user32.sends, 1)

        cases = {
            "lost focus": lambda native: setattr(native.user32, "foreground", 999),
            "closed target": lambda native: setattr(native.user32, "live", False),
            "replaced target": lambda native: setattr(
                native, "_window_pid", lambda _hwnd: 99
            ),
            "unexpected dialog": lambda native: setattr(
                native.user32, "foreground", 101
            ),
            "stopped process": lambda native: setattr(
                native,
                "_assert_process_live",
                lambda: (_ for _ in ()).throw(ValueError("retained process exited")),
            ),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                native = new_native()
                mutate(native)
                with self.assertRaisesRegex(ValueError, "input target"):
                    native._send([native._key("ENTER")])
                self.assertEqual(native.user32.sends, 0)


if __name__ == "__main__":
    unittest.main()
