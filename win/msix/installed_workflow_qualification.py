"""Drive and independently verify DayQuay's installed consumer workflow."""

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import zipfile


MANIFEST_NAME = "dayquay-manifest.json"
MONTH_NAME = re.compile(r"^[0-9]{4}-[0-9]{2}\.txt$")
RESTORE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
JOURNAL_DIRECTORY_CHOOSER_TITLE = "Select a directory"


def _windows_chooser_path(path):
    # GTK 3.24.52 splits its location entry at G_DIR_SEPARATOR (backslash
    # on Windows). UCRT Python can spell the same local path with slashes.
    # Keep this conversion at the chooser boundary, not in general text input.
    return str(path).replace("/", "\\")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _is_link_or_reparse(path):
    info = path.lstat()
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & reparse
    )


def _regular_tree(root):
    root = Path(root)
    if not root.is_dir() or _is_link_or_reparse(root):
        raise ValueError(f"journal is not a regular directory: {root}")
    files = {}
    for path in sorted(root.rglob("*")):
        if _is_link_or_reparse(path):
            raise ValueError(f"journal contains a link or reparse point: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"journal contains a non-file entry: {path}")
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        files[relative] = {
            "bytes": len(data),
            "sha256": _sha256(data),
            "content": data,
        }
    return files


def _public_files(files):
    return {
        relative: {"bytes": record["bytes"], "sha256": record["sha256"]}
        for relative, record in files.items()
    }


def capture_journal(journal, sentinel, additional_text=()):
    required_text = (sentinel, *additional_text)
    if any(not value or len(value) > 256 or not value.isascii() for value in required_text):
        raise ValueError("qualification text must be bounded nonempty ASCII")
    if len(set(required_text)) != len(required_text):
        raise ValueError("qualification text markers must be distinct")
    files = _regular_tree(Path(journal))
    if len(files) != 1:
        raise ValueError("saved journal must contain exactly one regular month file")
    relative, record = next(iter(files.items()))
    if "/" in relative or not MONTH_NAME.fullmatch(relative):
        raise ValueError("saved journal entry is not exactly one root month file")
    try:
        text = record["content"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("saved journal month is not UTF-8") from exc
    for value in required_text:
        if text.count(value) != 1:
            raise ValueError("saved journal does not contain each qualification marker once")
    return {
        "journal_root": str(Path(journal).resolve()),
        "sentinel_sha256": _sha256(sentinel.encode("ascii")),
        "additional_text_sha256": [
            _sha256(value.encode("ascii")) for value in additional_text
        ],
        "files": _public_files(files),
    }


def _require_same_files(actual, saved, label):
    if actual["files"] != saved["files"]:
        raise ValueError(f"{label} differs from saved journal exact bytes")
    if actual["sentinel_sha256"] != saved["sentinel_sha256"]:
        raise ValueError(f"{label} differs from saved journal sentinel")
    return actual


def verify_reopened(journal, sentinel, reopen_marker, saved):
    try:
        actual = capture_journal(journal, sentinel, (reopen_marker,))
    except ValueError as exc:
        raise ValueError(f"reopened journal is invalid: {exc}") from exc
    if set(actual["files"]) != set(saved["files"]):
        raise ValueError("reopened journal changed the saved month-file identity")
    if actual["files"] == saved["files"]:
        raise ValueError("reopened journal did not persist the post-transition marker")
    for relative, record in actual["files"].items():
        if record["bytes"] <= saved["files"][relative]["bytes"]:
            raise ValueError("reopened journal did not append consumer content")
    return actual


def verify_backup(archive_path, saved):
    archive_path = Path(archive_path)
    if not archive_path.is_file() or _is_link_or_reparse(archive_path):
        raise ValueError("backup is absent or is not a regular file")
    expected = saved["files"]
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or set(names) != set(expected) | {MANIFEST_NAME}:
                raise ValueError("backup entries differ from saved journal")
            for info in infos:
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise ValueError("backup contains a symbolic-link member")
            manifest = json.loads(archive.read(MANIFEST_NAME))
            if set(manifest) != {"created_at", "entries", "format", "version"}:
                raise ValueError("backup manifest schema differs")
            if manifest["format"] != "dayquay-backup" or manifest["version"] != 1:
                raise ValueError("backup format/version differs")
            manifest_files = {
                entry["path"]: {"bytes": entry["size"], "sha256": entry["sha256"]}
                for entry in manifest["entries"]
                if type(entry) is dict and set(entry) == {"path", "sha256", "size"}
            }
            if len(manifest_files) != len(manifest["entries"]) or manifest_files != expected:
                raise ValueError("backup manifest differs from saved journal")
            for relative, record in expected.items():
                data = archive.read(relative)
                if len(data) != record["bytes"] or _sha256(data) != record["sha256"]:
                    raise ValueError("backup payload differs from saved journal")
            if archive.testzip() is not None:
                raise ValueError("backup CRC verification failed")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"backup inspection failed: {exc}") from exc
    return {
        "archive": str(archive_path.resolve()),
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": _sha256(archive_path.read_bytes()),
        "files": expected,
        "manifest_verified": True,
    }


def verify_restored(journal, sentinel, reopen_marker, saved):
    try:
        actual = capture_journal(journal, sentinel, (reopen_marker,))
    except ValueError as exc:
        raise ValueError(f"restored journal is invalid: {exc}") from exc
    return _require_same_files(actual, saved, "restored journal")


def verify_protected_journal(journal, sentinel, reopen_marker, saved):
    try:
        actual = capture_journal(journal, sentinel, (reopen_marker,))
    except ValueError as exc:
        raise ValueError(f"original journal after restore is invalid: {exc}") from exc
    return _require_same_files(actual, saved, "original journal after restore")


def verify_protected_backup(archive, saved, original_backup):
    try:
        actual = verify_backup(archive, saved)
    except ValueError as exc:
        raise ValueError(f"backup after restore is invalid: {exc}") from exc
    for field in ("archive", "archive_bytes", "archive_sha256", "files"):
        if actual[field] != original_backup[field]:
            raise ValueError("backup after restore differs from its protected bytes")
    return actual


def restored_window_title(initial_title, restore_name):
    if not RESTORE_NAME.fullmatch(restore_name or ""):
        raise ValueError("invalid restore qualification folder name")
    prefix = "DayQuay - "
    if not initial_title.startswith(prefix) or initial_title.count(" - ") != 1:
        raise ValueError("initial title is not the default journal title contract")
    return f"DayQuay - {restore_name} - {initial_title[len(prefix):]}"


def _eventually(operation, label, timeout=15.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            return operation()
        except (FileNotFoundError, OSError, ValueError) as exc:
            last = exc
            time.sleep(0.1)
    raise ValueError(f"timed out waiting for {label}: {last}")


def run_consumer_workflow(
    *,
    ui,
    journal,
    archive,
    restore_parent,
    restore_name,
    sentinel,
    reopen_marker,
    initial_title,
):
    journal = Path(journal)
    archive = Path(archive)
    restore_parent = Path(restore_parent)
    restored = restore_parent / restore_name
    reopen_probe = restore_parent / "ReopenProbe"
    if not journal.is_absolute() or not archive.is_absolute() or not restore_parent.is_absolute():
        raise ValueError("workflow paths must be absolute")
    if restored.exists() or restored.is_symlink():
        raise ValueError("restore qualification destination already exists")
    if _regular_tree(reopen_probe):
        raise ValueError("reopen transition journal must be an empty regular directory")
    restored_title = restored_window_title(initial_title, restore_name)
    reopen_title = restored_window_title(initial_title, reopen_probe.name)

    ui.replace_editor_text(sentinel)
    ui.save()
    saved = _eventually(lambda: capture_journal(journal, sentinel), "consumer save")

    transition = ui.reopen_journal(journal, reopen_probe, reopen_title, initial_title)
    expected_transition = {"away_title": reopen_title, "return_title": initial_title}
    if transition != expected_transition:
        raise ValueError("reopen lacks an observable journal transition away and back")
    ui.append_editor_text(reopen_marker)
    ui.save()
    reopened = _eventually(
        lambda: verify_reopened(journal, sentinel, reopen_marker, saved),
        "consumer journal reopen",
    )

    ui.create_backup(archive)
    backup = _eventually(lambda: verify_backup(archive, reopened), "consumer backup")

    ui.restore_backup(archive, restore_parent, restore_name, restored_title)
    restored_record = _eventually(
        lambda: verify_restored(restored, sentinel, reopen_marker, reopened),
        "consumer restore",
    )
    original_after_restore = _eventually(
        lambda: verify_protected_journal(
            journal, sentinel, reopen_marker, reopened
        ),
        "original journal after restore",
    )
    backup_after_restore = _eventually(
        lambda: verify_protected_backup(archive, reopened, backup),
        "backup after restore",
    )

    return {
        "schema_version": 1,
        "input_method": "owned Win32 SendInput keyboard/mouse",
        "journal_backup_restore_workflow_tested": True,
        "sentinel_sha256": saved["sentinel_sha256"],
        "saved": saved,
        "reopen_transition": transition,
        "reopened": reopened,
        "backup": backup,
        "restored": restored_record,
        "original_after_restore": original_after_restore,
        "backup_after_restore": backup_after_restore,
        "restored_window_title": restored_title,
    }


class _WindowsInput:
    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 258
    WAIT_FAILED = 0xFFFFFFFF
    VK = {
        "CTRL": 0x11,
        "ALT": 0x12,
        "ENTER": 0x0D,
        "DOWN": 0x28,
        "UP": 0x26,
        "END": 0x23,
    }

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.WPARAM),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.WPARAM),
        ]

    class _INPUTUNION(ctypes.Union):
        pass

    class INPUT(ctypes.Structure):
        pass

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
            ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
            ("rcCaret", wintypes.RECT),
        ]

    _INPUTUNION._fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
    INPUT._anonymous_ = ("value",)
    INPUT._fields_ = [("type", wintypes.DWORD), ("value", _INPUTUNION)]

    def __init__(self, process_id, main_hwnd, main_title):
        if sys.platform != "win32":
            raise RuntimeError("installed consumer input requires native Windows")
        self.process_id = int(process_id)
        self.main_hwnd = int(main_hwnd)
        self.current_title = main_title
        self._input_hwnd = None
        self._input_title = None
        self._diagnostic_trace = []
        self._path_selection = None
        self._wait_condition = None
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_user32()
        self._configure_kernel32()
        self.process_handle = self.kernel32.OpenProcess(
            self.SYNCHRONIZE, False, self.process_id
        )
        if not self.process_handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def _configure_user32(self):
        callback_factory = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        self._enum_callback_type = callback_factory(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        self.user32.EnumWindows.argtypes = (self._enum_callback_type, wintypes.LPARAM)
        self.user32.EnumWindows.restype = wintypes.BOOL
        self.user32.GetForegroundWindow.argtypes = ()
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        self.user32.GetWindowRect.restype = wintypes.BOOL
        self.user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        self.user32.GetWindowTextW.argtypes = (
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        )
        self.user32.GetWindowTextW.restype = ctypes.c_int
        self.user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        self.user32.GetClassNameW.restype = ctypes.c_int
        self.user32.GetGUIThreadInfo.argtypes = (
            wintypes.DWORD, ctypes.POINTER(self.GUITHREADINFO),
        )
        self.user32.GetGUIThreadInfo.restype = wintypes.BOOL
        self.user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        )
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.IsWindow.argtypes = (wintypes.HWND,)
        self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.IsWindowEnabled.argtypes = (wintypes.HWND,)
        self.user32.IsWindowEnabled.restype = wintypes.BOOL
        self.user32.IsWindowVisible.argtypes = (wintypes.HWND,)
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        self.user32.SendInput.argtypes = (
            wintypes.UINT,
            ctypes.POINTER(self.INPUT),
            ctypes.c_int,
        )
        self.user32.SendInput.restype = wintypes.UINT
        self.user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
        self.user32.SetCursorPos.restype = wintypes.BOOL
        self.user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
        self.user32.ShowWindow.restype = wintypes.BOOL

    def _configure_kernel32(self):
        self.kernel32.OpenProcess.argtypes = (
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        )
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self.kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.kernel32.CloseHandle.restype = wintypes.BOOL

    def _assert_process_live(self):
        state = self.kernel32.WaitForSingleObject(self.process_handle, 0)
        if state == self.WAIT_TIMEOUT:
            return
        if state == self.WAIT_FAILED:
            raise ctypes.WinError(ctypes.get_last_error())
        if state == self.WAIT_OBJECT_0:
            raise ValueError("retained broker process has exited")
        raise ValueError(f"unexpected retained-process wait state: {state}")

    def close(self):
        if getattr(self, "process_handle", None):
            if not self.kernel32.CloseHandle(self.process_handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.process_handle = None

    def _window_pid(self, hwnd):
        owner = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(owner))
        return owner.value

    def _title(self, hwnd):
        length = self.user32.GetWindowTextLengthW(wintypes.HWND(hwnd))
        value = ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(wintypes.HWND(hwnd), value, len(value))
        return value.value

    def _assert_owned(self, hwnd, title=None):
        native_hwnd = wintypes.HWND(hwnd)
        if (
            not self.user32.IsWindow(native_hwnd)
            or not self.user32.IsWindowVisible(native_hwnd)
            or not self.user32.IsWindowEnabled(native_hwnd)
        ):
            raise ValueError("consumer input target is not a visible enabled live window")
        if self._window_pid(hwnd) != self.process_id:
            raise ValueError("consumer input target is not owned by the broker process")
        actual = self._title(hwnd)
        if title is not None and actual != title:
            raise ValueError(f"consumer input window title differs: {actual!r}")
        return actual

    def _owned_windows(self):
        result = []

        @self._enum_callback_type
        def collect(hwnd, _parameter):
            if self.user32.IsWindowVisible(hwnd) and self._window_pid(hwnd) == self.process_id:
                title = self._title(hwnd)
                if title:
                    result.append((int(hwnd), title))
            return True

        if not self.user32.EnumWindows(collect, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def _foreground(self, hwnd, title):
        self._assert_owned(hwnd, title)
        self.user32.ShowWindow(wintypes.HWND(hwnd), 9)
        for _attempt in range(20):
            self.user32.SetForegroundWindow(wintypes.HWND(hwnd))
            foreground = int(self.user32.GetForegroundWindow() or 0)
            if foreground == hwnd and self._window_pid(foreground) == self.process_id:
                self._input_hwnd = hwnd
                self._input_title = title
                return
            time.sleep(0.1)
        raise ValueError("owned consumer window could not become foreground")

    def _send(self, values):
        if self._input_hwnd is None or self._input_title is None:
            raise ValueError("input target is not pinned")
        try:
            self._assert_process_live()
            self._assert_owned(self._input_hwnd, self._input_title)
        except (OSError, ValueError) as exc:
            raise ValueError(f"input target ownership changed: {exc}") from exc
        foreground = int(self.user32.GetForegroundWindow() or 0)
        if foreground != self._input_hwnd:
            raise ValueError("input target is no longer the exact foreground HWND")
        if self._window_pid(foreground) != self.process_id:
            raise ValueError("input target foreground process changed")
        inputs = (self.INPUT * len(values))(*values)
        sent = self.user32.SendInput(len(inputs), inputs, ctypes.sizeof(self.INPUT))
        if sent != len(inputs):
            raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(0.08)

    def _key(self, value, key_up=False):
        key = self.VK[value] if value in self.VK else ord(value.upper())
        flags = self.KEYEVENTF_KEYUP if key_up else 0
        return self.INPUT(type=self.INPUT_KEYBOARD, ki=self.KEYBDINPUT(key, 0, flags, 0, 0))

    def chord(self, *keys):
        values = [self._key(key) for key in keys]
        values.extend(self._key(key, True) for key in reversed(keys))
        self._send(values)

    def press(self, key, count=1):
        for _ in range(count):
            self._send([self._key(key), self._key(key, True)])

    def text(self, value):
        units = value.encode("utf-16-le")
        inputs = []
        for index in range(0, len(units), 2):
            scan = int.from_bytes(units[index : index + 2], "little")
            inputs.extend(
                (
                    self.INPUT(
                        type=self.INPUT_KEYBOARD,
                        ki=self.KEYBDINPUT(0, scan, self.KEYEVENTF_UNICODE, 0, 0),
                    ),
                    self.INPUT(
                        type=self.INPUT_KEYBOARD,
                        ki=self.KEYBDINPUT(
                            0, scan, self.KEYEVENTF_UNICODE | self.KEYEVENTF_KEYUP, 0, 0
                        ),
                    ),
                )
            )
        self._send(inputs)

    def _wait_window(self, title, present=True, timeout=12.0):
        self._wait_condition = {"title": title, "present": present, "timeout_seconds": timeout, "status": "waiting"}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            matches = [item for item in self._owned_windows() if item[1] == title]
            if bool(matches) == present:
                if not present:
                    self._wait_condition["status"] = "satisfied"
                    return None
                if len(matches) != 1:
                    self._wait_condition["status"] = "ambiguous"
                    raise ValueError(f"ambiguous owned consumer window: {title}")
                self._wait_condition["status"] = "satisfied"
                return matches[0][0]
            time.sleep(0.1)
        state = [title for _hwnd, title in self._owned_windows()]
        self._wait_condition["status"] = "timed_out"
        raise ValueError(
            f"timed out waiting for consumer window {title!r}, present={present}: {state}"
        )

    def _diagnostic_window(self, hwnd):
        hwnd = int(hwnd or 0)
        live = bool(hwnd and self.user32.IsWindow(wintypes.HWND(hwnd)))
        owned = live and self._window_pid(hwnd) == self.process_id
        record = {"hwnd": hwnd, "live": live, "owned": owned}
        if owned:
            class_name = ctypes.create_unicode_buffer(256)
            self.user32.GetClassNameW(wintypes.HWND(hwnd), class_name, len(class_name))
            record.update(
                title=self._title(hwnd)[:512], class_name=class_name.value,
                visible=bool(self.user32.IsWindowVisible(wintypes.HWND(hwnd))),
                enabled=bool(self.user32.IsWindowEnabled(wintypes.HWND(hwnd))),
            )
        return record

    def _observe_diagnostic_state(self):
        self._assert_process_live()
        target = self._diagnostic_window(self._input_hwnd)
        state = {
            "input_target": target,
            "foreground": self._diagnostic_window(self.user32.GetForegroundWindow()),
            "owned_windows": [self._diagnostic_window(hwnd) for hwnd, _ in self._owned_windows()[:16]],
            "focus_scope": "Win32 HWND focus; GTK widget/default-button focus may require the failure screenshot",
        }
        if target["owned"]:
            owner = wintypes.DWORD()
            thread = self.user32.GetWindowThreadProcessId(wintypes.HWND(target["hwnd"]), ctypes.byref(owner))
            if owner.value != self.process_id:
                raise ValueError("diagnostic window ownership changed")
            info = self.GUITHREADINFO()
            info.cbSize = ctypes.sizeof(info)
            if not self.user32.GetGUIThreadInfo(thread, ctypes.byref(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            state.update(
                gui_thread_id=int(thread), gui_flags=int(info.flags),
                active=self._diagnostic_window(info.hwndActive),
                focus=self._diagnostic_window(info.hwndFocus),
                caret=self._diagnostic_window(info.hwndCaret),
            )
        return state

    def _record_diagnostic_step(self, step):
        try:
            state = self._observe_diagnostic_state()
        except Exception as exc:
            state = {"observation_error": str(exc)[:1024]}
        trace = getattr(self, "_diagnostic_trace", [])
        trace.append({"step": step, "selection": self._path_selection, "state": state})
        self._diagnostic_trace = trace[-32:]

    def failure_diagnostics(self):
        try:
            state = self._observe_diagnostic_state()
        except Exception as exc:
            state = {"observation_error": str(exc)[:1024]}
        return {
            "wait_condition": getattr(self, "_wait_condition", None),
            "path_selection": getattr(self, "_path_selection", None),
            "input_target": {"hwnd": self._input_hwnd, "title": self._input_title},
            "trace": getattr(self, "_diagnostic_trace", []), "failure_state": state,
        }

    def _main(self, title=None):
        expected = self.current_title if title is None else title
        self._foreground(self.main_hwnd, expected)

    def _select_path(self, dialog_title, path, accept_key):
        input_text = _windows_chooser_path(path)
        self._path_selection = {
            "dialog_title": dialog_title, "path": str(path)[:4096], "accept_key": accept_key,
            "input_text": input_text[:4096],
        }
        try:
            self._path_selection.update(
                exists=Path(path).exists(), is_directory=Path(path).is_dir(),
                parent_exists=Path(path).parent.exists(),
            )
        except OSError as exc:
            self._path_selection["observation_error"] = str(exc)[:1024]
        hwnd = self._wait_window(dialog_title)
        self._foreground(hwnd, dialog_title)
        self._record_diagnostic_step("dialog_foreground")
        self.chord("CTRL", "L")
        self._record_diagnostic_step("after_ctrl_l")
        # GTK's SAVE chooser selects the filename stem, leaving its extension.
        # Replace the whole location/name so a prefilled .zip cannot be appended.
        self.chord("CTRL", "A")
        self._record_diagnostic_step("after_ctrl_a")
        self.text(input_text)
        self._record_diagnostic_step("after_path_text")
        self.press("ENTER")
        self._record_diagnostic_step("after_enter")
        time.sleep(0.5)
        if any(item[0] == hwnd for item in self._owned_windows()):
            self._foreground(hwnd, dialog_title)
            self.chord("ALT", accept_key)
            self._record_diagnostic_step("after_accept_key")
        self._wait_window(dialog_title, present=False)

    def _click_editor(self):
        rectangle = wintypes.RECT()
        if not self.user32.GetWindowRect(wintypes.HWND(self.main_hwnd), ctypes.byref(rectangle)):
            raise ctypes.WinError(ctypes.get_last_error())
        width = rectangle.right - rectangle.left
        height = rectangle.bottom - rectangle.top
        if width < 400 or height < 300:
            raise ValueError("owned main window is too small for editor input")
        x = rectangle.left + (width * 2 // 3)
        y = rectangle.top + (height // 2)
        if not self.user32.SetCursorPos(x, y):
            raise ctypes.WinError(ctypes.get_last_error())
        self._send(
            [
                self.INPUT(
                    type=self.INPUT_MOUSE,
                    mi=self.MOUSEINPUT(0, 0, 0, self.MOUSEEVENTF_LEFTDOWN, 0, 0),
                ),
                self.INPUT(
                    type=self.INPUT_MOUSE,
                    mi=self.MOUSEINPUT(0, 0, 0, self.MOUSEEVENTF_LEFTUP, 0, 0),
                ),
            ]
        )

    def replace_editor_text(self, text):
        self._main()
        self._click_editor()
        self.chord("CTRL", "A")
        self.text(text)

    def append_editor_text(self, text):
        self._main()
        self._click_editor()
        self.chord("CTRL", "END")
        self.text("\n" + text)

    def save(self):
        self._main()
        self.chord("CTRL", "S")

    def reopen_journal(self, path, transition_path, transition_title, return_title):
        self._main()
        self.chord("CTRL", "N")
        self._select_path(JOURNAL_DIRECTORY_CHOOSER_TITLE, transition_path, "O")
        self._wait_window(transition_title)
        self._assert_owned(self.main_hwnd, transition_title)
        self.current_title = transition_title

        self._main()
        self.chord("CTRL", "O")
        self._select_path(JOURNAL_DIRECTORY_CHOOSER_TITLE, path, "O")
        self._wait_window(return_title)
        self._assert_owned(self.main_hwnd, return_title)
        self.current_title = return_title
        return {"away_title": transition_title, "return_title": return_title}

    def create_backup(self, path):
        self._main()
        self.chord("ALT", "J")
        self.press("B")
        self._select_path("Select backup filename", path, "S")

    def restore_backup(self, archive, _parent, name, expected_title):
        self._main()
        self.chord("ALT", "J")
        self.press("END")
        self.press("UP", 2)
        self.press("ENTER")
        self._select_path("Select a DayQuay portable backup", archive, "I")

        hwnd = self._wait_window("Restore portable backup")
        self._foreground(hwnd, "Restore portable backup")
        self.press("ENTER")
        self._wait_window("Restore portable backup", present=False)

        hwnd = self._wait_window("Choose a new journal folder")
        self._foreground(hwnd, "Choose a new journal folder")
        self.chord("ALT", "N")
        self.text(name)
        self.press("ENTER")
        self._wait_window("Choose a new journal folder", present=False)

        hwnd = self._wait_window("Restore complete")
        self._foreground(hwnd, "Restore complete")
        self.chord("ALT", "O")
        self._wait_window("Restore complete", present=False)
        self._wait_window(expected_title)
        self._assert_owned(self.main_hwnd, expected_title)
        self.current_title = expected_title


def _write_json_exclusive(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--process-id", required=True, type=int)
    parser.add_argument("--main-window-handle", required=True, type=int)
    parser.add_argument("--initial-title", required=True)
    parser.add_argument("--profile-root", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--restore-name", required=True)
    parser.add_argument("--sentinel", required=True)
    parser.add_argument("--reopen-marker", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    profile = args.profile_root.resolve(strict=True)
    journal = profile / "data"
    if journal.resolve(strict=True).parent != profile:
        parser.error("journal is outside the exact qualification profile")
    if args.archive.exists() or args.archive.is_symlink():
        parser.error("backup qualification output already exists")
    ui = None
    try:
        ui = _WindowsInput(args.process_id, args.main_window_handle, args.initial_title)
        evidence = run_consumer_workflow(
            ui=ui,
            journal=journal,
            archive=args.archive.absolute(),
            restore_parent=profile,
            restore_name=args.restore_name,
            sentinel=args.sentinel,
            reopen_marker=args.reopen_marker,
            initial_title=args.initial_title,
        )
        evidence["process_id"] = args.process_id
        evidence["main_window_handle"] = args.main_window_handle
        _write_json_exclusive(args.output, evidence)
    except (OSError, ValueError, RuntimeError) as exc:
        failure = {
            "schema_version": 1, "workflow_qualified": False, "error": str(exc),
            "process_id": args.process_id, "main_window_handle": args.main_window_handle,
            "diagnostics": ui.failure_diagnostics() if ui is not None else None,
        }
        try:
            _write_json_exclusive(args.output.with_name(args.output.stem + "-failure.json"), failure)
        except (OSError, ValueError) as diagnostic_error:
            parser.error(f"{exc}; failure diagnostics could not be retained: {diagnostic_error}")
        parser.error(str(exc))
    finally:
        if ui is not None:
            ui.close()


if __name__ == "__main__":
    main()
