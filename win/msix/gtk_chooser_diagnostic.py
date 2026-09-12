"""Observe the real GTK chooser and native input in a separate probe process.

This never qualifies the installed application. GTK signals are observed only;
the direct activate_default comparison is confined to this standalone process.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET

from installed_workflow_qualification import _WindowsInput, _is_link_or_reparse, _windows_chooser_path


MARKER = ".dayquay-chooser-probe-owner"
ACTIONS = ("enter", "alt_o", "activate_default")
PATH_STYLES = ("native", "forward_slash")


def chooser_target(path, path_style):
    if path_style == "native":
        return _windows_chooser_path(path)
    if path_style == "forward_slash":
        return str(path).replace("\\", "/")
    raise ValueError("unknown chooser diagnostic path spelling")


def chooser_xml(glade, chooser_id="dir_chooser"):
    if chooser_id not in ("dir_chooser", "backup_dialog"):
        raise ValueError("unknown diagnostic chooser")
    document = ET.parse(glade).getroot()
    matches = document.findall(f"object[@id='{chooser_id}']")
    if len(matches) != 1 or matches[0].get("class") != "GtkFileChooserDialog":
        raise ValueError("actual Glade does not contain one requested chooser")
    interface = ET.Element("interface")
    ET.SubElement(interface, "requires", {"lib": "gtk+", "version": "3.10"})
    interface.append(matches[0])
    return ET.tostring(interface, encoding="unicode")


def create_probe_tree():
    root = Path(tempfile.mkdtemp(prefix="dayquay-chooser-probe-"))
    token = uuid.uuid4().hex
    (root / MARKER).write_text(token, encoding="ascii")
    (root / "DayQuay" / "ReopenProbe").mkdir(parents=True)
    return root, token


def remove_probe_tree(root, token):
    """Refuse substitutions or unexpected data before deleting any owned entry."""
    root = Path(root)
    marker = root / MARKER
    parent = root / "DayQuay"
    probe = parent / "ReopenProbe"
    for path in (root, marker, parent, probe):
        if _is_link_or_reparse(path):
            raise ValueError("probe cleanup refused a link or reparse point")
    if not marker.is_file() or marker.read_text(encoding="ascii") != token:
        raise ValueError("probe cleanup ownership marker changed")
    # UCRT Python 3.14.7 enumerates mixed-separator WindowsPath objects that
    # compare unequal to the same joined paths (native run 34670828389).
    # Compare exact child names from the directory, not lexical full paths.
    if (
        set(os.listdir(root)) != {MARKER, "DayQuay"}
        or set(os.listdir(parent)) != {"ReopenProbe"}
        or os.listdir(probe)
    ):
        details = {}
        try:
            for label, directory, expected in (
                ("root", root, {MARKER, "DayQuay"}),
                ("parent", parent, {"ReopenProbe"}),
                ("probe", probe, set()),
            ):
                observed = set(os.listdir(directory))
                details[label] = {
                    "directory": str(directory)[:1024],
                    "path_type": type(directory).__name__,
                    "expected": sorted(str(p)[:1024] for p in expected),
                    "observed": sorted(str(p)[:1024] for p in observed)[:16],
                    "observed_count": len(observed),
                    "equal": observed == expected,
                }
        except Exception as error:
            details["observation_error"] = str(error)[:1024]
        raise ValueError("probe cleanup found unexpected entries: " + json.dumps(details))
    probe.rmdir()
    parent.rmdir()
    marker.unlink()
    root.rmdir()


def dispatch_action(native, hwnd, title, action, activate_default):
    if action not in ACTIONS:
        raise ValueError("unknown chooser diagnostic action")
    native._foreground(hwnd, title)
    if action == "enter":
        native.press("ENTER")
    elif action == "alt_o":
        native.chord("ALT", "O")
    else:
        return activate_default()


def run_case(Gtk, Gdk, GLib, glade, parent_folder, action, path_style,
             chooser_id="dir_chooser", select_all=False):
    saving = chooser_id == "backup_dialog"
    target_name = "DayQuay-consumer-backup.zip" if saving else "ReopenProbe"
    target = chooser_target(parent_folder / target_name, path_style)
    builder = Gtk.Builder()
    builder.add_from_string(chooser_xml(glade, chooser_id))
    dialog = builder.get_object(chooser_id)
    button = builder.get_object("button1" if saving else "button17")
    parent = Gtk.Window(title="DayQuay standalone chooser diagnostic")
    parent.set_default_size(992, 696)
    parent.show_all()
    dialog.set_transient_for(parent)
    dialog.set_current_folder(str(parent_folder))
    if saving:
        # Match Backup._get_backup_file for the default "data" journal.
        dialog.set_current_name(f"DayQuay-Backup-{datetime.date.today()}.zip")
        dialog.set_do_overwrite_confirmation(False)
        archive_filter = Gtk.FileFilter()
        archive_filter.set_name("Zip")
        archive_filter.add_pattern("*.zip")
        dialog.add_filter(archive_filter)
    title = dialog.get_title()
    loop = GLib.MainLoop()
    responded = threading.Event()
    record = {
        "action": action, "path_style": path_style, "target": target,
        "chooser_id": chooser_id, "select_all": select_all,
        "events": [], "dropped_events": 0,
    }
    hooked = set()

    def observe(kind, **fields):
        record["events"].append({"event": kind, "monotonic": time.monotonic(), **fields})
        if len(record["events"]) > 256:
            record["events"].pop(0)
            record["dropped_events"] += 1

    def widget_state(widget):
        if widget is None:
            return None
        state = {
            "type": widget.__gtype__.name,
            "visible": widget.get_visible(),
            "mapped": widget.get_mapped(),
            "sensitive": widget.is_sensitive(),
            "can_default": widget.get_can_default(),
            "has_default": widget.has_default(),
            "receives_default": widget.get_receives_default(),
            "is_ok_button": widget == button,
        }
        if isinstance(widget, Gtk.Entry):
            state.update(text=widget.get_text()[:4096], activates_default=widget.get_activates_default(),
                         selection=list(widget.get_selection_bounds()), cursor_position=widget.get_position())
        if isinstance(widget, Gtk.Button):
            state["label"] = widget.get_label()
        return state

    def snapshot():
        return {
            "focus": widget_state(dialog.get_focus()),
            "default": widget_state(dialog.get_default_widget()),
            "ok_response_widget": widget_state(dialog.get_widget_for_response(Gtk.ResponseType.OK)),
            "selected_path": dialog.get_filename(),
            "current_folder": dialog.get_current_folder(),
            "current_name": dialog.get_current_name() if saving else None,
            "dialog_visible": dialog.get_visible(),
            "action": int(dialog.get_action()),
        }

    def key_signal(widget, event, signal):
        if event.type in (Gdk.EventType.KEY_PRESS, Gdk.EventType.KEY_RELEASE):
            observe(
                signal, widget=widget.__gtype__.name,
                keyval=int(event.keyval), key_name=Gdk.keyval_name(event.keyval),
                hardware_keycode=int(event.hardware_keycode), modifiers=int(event.state),
                event_type=int(event.type),
            )
        return False

    def hook(widget):
        if widget in hooked:
            return
        hooked.add(widget)
        widget.connect("key-press-event", key_signal, "key-press-event")
        widget.connect("event-after", key_signal, "event-after")
        if isinstance(widget, Gtk.Entry):
            widget.connect("activate", lambda entry: observe("entry-activate", state=widget_state(entry)))
        if isinstance(widget, Gtk.Container):
            widget.connect("add", lambda container, child: hook(child))
            for child in widget.get_children():
                hook(child)

    def response(_dialog, response_id):
        observe("dialog-response", response_id=int(response_id), state=snapshot())
        record["response_id"] = int(response_id)
        responded.set()

    hook(dialog)
    button.connect("clicked", lambda _button: observe("ok-clicked", state=snapshot()))
    dialog.connect("response", response)
    dialog.connect("current-folder-changed", lambda _dialog: observe("folder-changed", state=snapshot()))
    dialog.show_all()

    def main_call(operation):
        completed = threading.Event()
        result = {}

        def invoke():
            try:
                result["value"] = operation()
            except Exception as exc:
                result["error"] = exc
            finally:
                completed.set()
            return False

        GLib.idle_add(invoke)
        if not completed.wait(5):
            raise TimeoutError("GTK main-thread diagnostic callback did not complete")
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def worker():
        native = None
        try:
            native = _WindowsInput(os.getpid(), 0, title)
            hwnd = native._wait_window(title, timeout=8)
            native._foreground(hwnd, title)
            record["owned_hwnd"] = hwnd
            record["before_input"] = main_call(snapshot)
            native.chord("CTRL", "L")
            # Ctrl+L can create the location entry after the initial tree walk.
            main_call(lambda: hook(dialog.get_focus()) if dialog.get_focus() else None)
            record["after_ctrl_l"] = main_call(snapshot)
            if select_all:
                native.chord("CTRL", "A")
                record["after_ctrl_a"] = main_call(snapshot)
            native.text(target)
            record["before_action"] = main_call(snapshot)
            record["native_before_action"] = native._observe_diagnostic_state()
            record["activate_default_return"] = dispatch_action(
                native, hwnd, title, action,
                lambda: main_call(dialog.activate_default),
            )
            record["response_observed"] = responded.wait(6)
            record["after_action"] = main_call(snapshot)
            selected = record["after_action"]["selected_path"]
            record["selected_path_matches_target"] = bool(selected) and (
                os.path.normcase(os.path.normpath(selected)) == os.path.normcase(os.path.normpath(target))
            )
            record["native_after_action"] = native._observe_diagnostic_state()
        except Exception as exc:
            record["probe_error"] = f"{type(exc).__name__}: {exc}"[:2048]
        finally:
            if native is not None:
                try:
                    native.close()
                except Exception as exc:
                    record["handle_cleanup_error"] = str(exc)[:1024]
            GLib.idle_add(lambda: loop.quit())

    thread = threading.Thread(target=worker, name="owned-native-input")
    thread.start()
    try:
        loop.run()
    finally:
        thread.join(timeout=1)
        dialog.destroy()
        parent.destroy()
    if thread.is_alive():
        raise RuntimeError("owned input worker did not stop")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glade", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = {
        "schema": "dayquay-standalone-gtk-chooser-diagnostic-v1",
        "diagnostic_only": True, "installed_workflow_qualified": False,
        "process_id": os.getpid(), "cases": [],
        "input_helper": "installed_workflow_qualification._WindowsInput",
    }
    root = token = None
    try:
        if sys.platform != "win32":
            raise RuntimeError("chooser native-input diagnostic requires Windows")
        import gi
        gi.require_version("Gdk", "3.0")
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, GLib, Gtk

        receipt["gtk_version"] = [Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()]
        receipt["glade_sha256"] = hashlib.sha256(args.glade.read_bytes()).hexdigest()
        receipt["chooser_subtree_sha256"] = hashlib.sha256(
            chooser_xml(args.glade).encode("utf-8")
        ).hexdigest()
        receipt["save_chooser_subtree_sha256"] = hashlib.sha256(
            chooser_xml(args.glade, "backup_dialog").encode("utf-8")
        ).hexdigest()
        receipt["input_helper_sha256"] = hashlib.sha256(
            Path(__file__).with_name("installed_workflow_qualification.py").read_bytes()
        ).hexdigest()
        root, token = create_probe_tree()
        receipt["owned_temporary_root"] = str(root)
        for path_style in PATH_STYLES:
            for action in ACTIONS:
                receipt["cases"].append(run_case(
                    Gtk, Gdk, GLib, args.glade, root / "DayQuay", action, path_style,
                ))
        # Compare the original SAVE sequence with full selection, using the
        # actual backup Glade and retained-process native input. No files are
        # created by this standalone chooser and it cannot qualify the app.
        for select_all in (False, True):
            receipt["cases"].append(run_case(
                Gtk, Gdk, GLib, args.glade, root / "DayQuay", "enter", "native",
                chooser_id="backup_dialog", select_all=select_all,
            ))
    except Exception as exc:
        receipt["probe_error"] = f"{type(exc).__name__}: {exc}"[:2048]
    finally:
        if root is not None:
            try:
                remove_probe_tree(root, token)
                receipt["owned_temporary_cleanup"] = "removed"
            except Exception as exc:
                receipt["owned_temporary_cleanup"] = "refused"
                receipt["cleanup_error"] = str(exc)[:1024]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return int(bool(receipt.get("probe_error") or receipt.get("cleanup_error") or any(
        case.get("probe_error") or case.get("handle_cleanup_error") for case in receipt["cases"]
    )))


if __name__ == "__main__":
    raise SystemExit(main())
