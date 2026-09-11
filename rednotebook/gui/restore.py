import os
from pathlib import Path

from rednotebook import restore


try:
    from gi.repository import Gtk
except ImportError:  # The controller remains testable without a GTK runtime.
    Gtk = None


def format_inspection_summary(inspection):
    noun = "file" if inspection.file_count == 1 else "files"
    return _(
        "Created: {created}\nContents: {count} {noun}, {size} bytes\n"
        "Every listed file and checksum passed inspection."
    ).format(
        created=inspection.created_at,
        count=inspection.file_count,
        noun=noun,
        size=inspection.total_bytes,
    )


def resolve_new_destination(parent, name):
    parent = Path(parent)
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError(_("Select a real existing parent folder."))
    name = name.strip()
    if (
        not name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
        or ":" in name
        or name.endswith((" ", "."))
    ):
        raise ValueError(_("Enter one valid new folder name."))
    destination = parent.resolve() / name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(_("The restore destination already exists."))
    return destination


class RestoreController:
    def __init__(self, journal):
        self.journal = journal

    def inspect(self, archive):
        return restore.inspect_backup(archive)

    def restore(self, archive, destination, inspection):
        try:
            return restore.restore_backup(archive, destination, inspection)
        except (OSError, ValueError, NotImplementedError) as exc:
            self.show_failure("restore", archive, exc)
            return None

    def open_restored(self, result):
        return self.journal.open_restored_journal(result.destination)

    def show_failure(self, operation, archive, error):
        message = _(
            'Portable backup {operation} failed for "{archive}": {error}\n\n'
            "The active journal was not changed. Fix the reported problem or choose "
            "another backup/destination and try again."
        ).format(operation=operation, archive=archive, error=error)
        self.journal.show_message(message, title=_("Portable backup error"), error=True)


class RestoreAssistant:
    def __init__(self, journal):
        if Gtk is None:
            raise RuntimeError("GTK is required for the restore assistant")
        self.journal = journal
        self.parent = journal.frame.main_frame
        self.controller = RestoreController(journal)

    def run(self):
        archive = self._select_backup()
        if archive is None:
            return None
        try:
            inspection = self.controller.inspect(archive)
        except (OSError, ValueError) as exc:
            self.controller.show_failure("inspection", archive, exc)
            return None
        if not self._confirm_inspection(archive, inspection):
            return None
        destination = self._select_destination()
        if destination is None:
            return None
        result = self.controller.restore(archive, destination, inspection)
        if result is None:
            return None
        if self._show_success(result):
            self.controller.open_restored(result)
        return result

    def _select_backup(self):
        dialog = Gtk.FileChooserDialog(
            title=_("Select a DayQuay portable backup"),
            parent=self.parent,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("_Inspect"), Gtk.ResponseType.OK
        )
        file_filter = Gtk.FileFilter()
        file_filter.set_name(_("ZIP backups"))
        file_filter.add_pattern("*.zip")
        dialog.add_filter(file_filter)
        response = dialog.run()
        selected = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        return selected

    def _confirm_inspection(self, archive, inspection):
        dialog = Gtk.MessageDialog(
            parent=self.parent,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_format=_("Portable backup passed inspection"),
        )
        dialog.set_title(_("Restore portable backup"))
        dialog.format_secondary_text(
            f'{archive}\n\n{format_inspection_summary(inspection)}\n\n'
            + _("Continue to choose a new journal folder.")
        )
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def _select_destination(self):
        dialog = Gtk.Dialog(
            title=_("Choose a new journal folder"),
            transient_for=self.parent,
            modal=True,
        )
        dialog.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("_Restore"), Gtk.ResponseType.OK
        )
        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_border_width(12)
        explanation = Gtk.Label(
            label=_(
                "Choose an existing parent folder and enter a new folder name. "
                "Restore never writes into an existing journal."
            )
        )
        explanation.set_line_wrap(True)
        explanation.set_xalign(0)
        content.pack_start(explanation, False, False, 0)
        parent_label = Gtk.Label.new_with_mnemonic(_("_Parent folder:"))
        parent_label.set_xalign(0)
        chooser = Gtk.FileChooserButton.new(
            _("Select parent folder"), Gtk.FileChooserAction.SELECT_FOLDER
        )
        chooser.set_filename(os.path.dirname(self.journal.dirs.data_dir))
        parent_label.set_mnemonic_widget(chooser)
        content.pack_start(parent_label, False, False, 0)
        content.pack_start(chooser, False, False, 0)
        name_label = Gtk.Label.new_with_mnemonic(_("New folder _name:"))
        name_label.set_xalign(0)
        name_entry = Gtk.Entry()
        name_entry.set_activates_default(True)
        name_label.set_mnemonic_widget(name_entry)
        content.pack_start(name_label, False, False, 0)
        content.pack_start(name_entry, False, False, 0)
        error_label = Gtk.Label()
        error_label.set_xalign(0)
        content.pack_start(error_label, False, False, 0)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        destination = None
        while dialog.run() == Gtk.ResponseType.OK:
            try:
                destination = resolve_new_destination(chooser.get_filename(), name_entry.get_text())
            except (OSError, ValueError) as exc:
                error_label.set_text(str(exc))
                continue
            break
        dialog.destroy()
        return destination

    def _show_success(self, result):
        dialog = Gtk.MessageDialog(
            parent=self.parent,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            message_format=_("Portable backup restored and verified"),
        )
        dialog.set_title(_("Restore complete"))
        dialog.format_secondary_text(
            _("Restored {count} files ({size} bytes) to:\n{destination}").format(
                count=result.file_count,
                size=result.total_bytes,
                destination=result.destination,
            )
        )
        dialog.add_button(_("_Keep current journal"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("_Open restored journal"), Gtk.ResponseType.ACCEPT)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.ACCEPT
