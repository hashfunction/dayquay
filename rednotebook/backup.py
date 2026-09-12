# -----------------------------------------------------------------------
# Copyright (c) 2008-2024 Jendrik Seipp
#
# RedNotebook is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# RedNotebook is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with RedNotebook; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# -----------------------------------------------------------------------

import datetime
import hashlib
import json
import logging
import os
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


DATE_FORMAT = "%Y-%m-%d"
MAX_BACKUP_AGE = 7
BACKUP_NOW = 100
ASK_NEXT_TIME = 200
NEVER_ASK_AGAIN = 300
MANIFEST_NAME = "dayquay-manifest.json"
COPY_CHUNK_SIZE = 1024 * 1024


class InvalidBackupSource(ValueError):
    pass


@dataclass(frozen=True)
class BackupResult:
    archive_path: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True)
class BackupFileIdentity:
    device: int
    inode: int
    size: int
    sha256: str


@dataclass(frozen=True)
class BackupSelection:
    path: str
    overwrite: bool = False
    approved_identity: BackupFileIdentity = None


def _capture_file_identity(path):
    """Capture a stable identity and content digest for a regular file."""
    path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InvalidBackupSource(f'Backup destination cannot be inspected: "{path}"') from exc
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise InvalidBackupSource(f'Backup destination is not a regular file: "{path}"')
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            while chunk := stream.read(COPY_CHUNK_SIZE):
                digest.update(chunk)
            after = os.fstat(stream.fileno())
    finally:
        if descriptor is not None:
            os.close(descriptor)
    stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
        raise InvalidBackupSource(f'Backup destination changed while inspected: "{path}"')
    try:
        current = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise InvalidBackupSource(f'Backup destination changed while inspected: "{path}"') from exc
    if stat.S_ISLNK(current.st_mode) or any(
        getattr(after, field) != getattr(current, field) for field in stable_fields
    ):
        raise InvalidBackupSource(f'Backup destination changed while inspected: "{path}"')
    return BackupFileIdentity(
        device=after.st_dev,
        inode=after.st_ino,
        size=after.st_size,
        sha256=digest.hexdigest(),
    )


def _source_entries(files, base_dir, arc_base_dir=""):
    root = Path(base_dir or os.curdir).resolve(strict=True)
    prefix = PurePosixPath(str(arc_base_dir).replace("\\", "/"))
    entries = []
    seen = set()
    for value in files:
        source = Path(value)
        if source.is_symlink():
            raise InvalidBackupSource(f'Backup source is a symbolic link: "{source}"')
        try:
            resolved = source.resolve(strict=True)
            relative = resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise InvalidBackupSource(f'Backup source is outside journal: "{source}"') from exc
        if not resolved.is_file():
            raise InvalidBackupSource(f'Backup source is not a regular file: "{source}"')
        member = prefix.joinpath(*relative.parts)
        member_name = member.as_posix().lstrip("/")
        if not member_name or member_name == MANIFEST_NAME or member_name in seen:
            raise InvalidBackupSource(f'Unsafe or duplicate archive path: "{member_name}"')
        seen.add(member_name)
        entries.append((member_name, resolved))
    return sorted(entries, key=lambda item: item[0])


def _stream_member(archive, member_name, source):
    digest = hashlib.sha256()
    size = 0
    source_stat = source.stat(follow_symlinks=False)
    if not stat.S_ISREG(source_stat.st_mode):
        raise InvalidBackupSource(f'Backup source is not a regular file: "{source}"')
    with source.open("rb") as input_file, archive.open(member_name, "w") as output_file:
        while chunk := input_file.read(COPY_CHUNK_SIZE):
            output_file.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return {"path": member_name, "sha256": digest.hexdigest(), "size": size}


def _manifest(entries):
    return {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "entries": entries,
        "format": "dayquay-backup",
        "version": 1,
    }


def build_manifest(data_dir, files):
    entries = []
    for member_name, source in _source_entries(files, data_dir):
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as input_file:
            while chunk := input_file.read(COPY_CHUNK_SIZE):
                digest.update(chunk)
                size += len(chunk)
        entries.append({"path": member_name, "sha256": digest.hexdigest(), "size": size})
    return _manifest(entries)


def _publish_no_replace(staged, destination):
    """Atomically publish a sibling file while preserving any existing destination."""
    try:
        os.link(staged, destination, follow_symlinks=False)
    except FileExistsError:
        raise
    except OSError as exc:
        raise OSError(f'Atomic no-replace publish failed for "{destination}": {exc}') from exc
    os.unlink(staged)


def _publish_approved_replace(staged, destination, approved_identity):
    """Replace only the exact file moved atomically out of the destination path."""
    if approved_identity is None:
        raise InvalidBackupSource("Overwrite approval is missing the selected file identity")
    descriptor, displaced_name = tempfile.mkstemp(
        prefix=f".{destination.name}.approved-", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    displaced = Path(displaced_name)
    moved = False
    try:
        try:
            os.replace(destination, displaced)
            moved = True
        except OSError as exc:
            raise InvalidBackupSource(
                f'Approved backup destination changed before publication: "{destination}"'
            ) from exc
        try:
            actual_identity = _capture_file_identity(displaced)
        except InvalidBackupSource as exc:
            actual_identity = None
            identity_error = exc
        else:
            identity_error = None
        if actual_identity != approved_identity:
            try:
                _publish_no_replace(displaced, destination)
                moved = False
            except FileExistsError as exc:
                raise InvalidBackupSource(
                    "Approved backup destination was replaced; the displaced file is retained "
                    f'at "{displaced}"'
                ) from exc
            raise InvalidBackupSource(
                f'Approved backup destination was replaced: "{destination}"'
            ) from identity_error
        try:
            _publish_no_replace(staged, destination)
        except FileExistsError as exc:
            raise InvalidBackupSource(
                "Backup destination reappeared during publication; the approved original is "
                f'retained at "{displaced}"'
            ) from exc
        moved = False
    finally:
        if not moved:
            try:
                displaced.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                logging.warning("Could not remove displaced backup %s: %s", displaced, exc)


def write_archive(
    archive_file_name,
    files,
    base_dir="",
    arc_base_dir="",
    *,
    overwrite=False,
    approved_identity=None,
):
    """Write a portable archive and publish it after full integrity verification."""
    from rednotebook import restore

    if base_dir:
        try:
            restore.validate_journal_directory(base_dir)
        except restore.InvalidBackup as exc:
            raise InvalidBackupSource(f"Journal is not portable: {exc}") from exc
    requested_destination = Path(archive_file_name)
    if requested_destination.is_symlink():
        raise InvalidBackupSource(
            f'Backup destination is a symbolic link: "{requested_destination}"'
        )
    requested_destination.parent.mkdir(parents=True, exist_ok=True)
    destination = requested_destination.parent.resolve() / requested_destination.name
    entries = [
        (member, source)
        for member, source in _source_entries(files, base_dir, arc_base_dir)
        if source != destination
    ]
    descriptor, staged_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    staged = Path(staged_name)
    manifest_entries = []
    try:
        # Store journal members without compression so any valid backup also
        # satisfies restore's decompression-ratio policy by construction.
        with zipfile.ZipFile(staged, mode="w", compression=zipfile.ZIP_STORED) as archive:
            for member_name, source in entries:
                manifest_entries.append(_stream_member(archive, member_name, source))
            archive.writestr(
                MANIFEST_NAME,
                json.dumps(
                    _manifest(manifest_entries), ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8"),
            )
        # Windows' CRT rejects fsync() on a read-only descriptor.
        with staged.open("r+b") as staged_file:
            os.fsync(staged_file.fileno())
        with zipfile.ZipFile(staged) as archive:
            if failed_member := archive.testzip():
                raise OSError(f'Backup verification failed for member "{failed_member}"')
            json.loads(archive.read(MANIFEST_NAME))
        try:
            restore.inspect_backup(staged)
        except restore.InvalidBackup as exc:
            raise InvalidBackupSource(f"Portable backup validation failed: {exc}") from exc
        if overwrite:
            _publish_approved_replace(staged, destination, approved_identity)
        else:
            _publish_no_replace(staged, destination)
        return BackupResult(
            archive_path=str(destination),
            file_count=len(manifest_entries),
            total_bytes=sum(entry["size"] for entry in manifest_entries),
        )
    finally:
        try:
            staged.unlink()
        except FileNotFoundError:
            pass


class Archiver:
    def __init__(self, journal):
        self.journal = journal

    def check_last_backup_date(self):
        from gi.repository import Gtk

        last_backup_age = self._last_backup_age()
        if last_backup_age <= MAX_BACKUP_AGE:
            return

        logging.warning(f"Last backup is older than {MAX_BACKUP_AGE} days.")
        text1 = _(f"It has been {last_backup_age} days since you made your last backup.")
        text2 = _("You can backup your journal to a zip file to avoid data loss.")
        dialog = Gtk.MessageDialog(
            parent=self.journal.frame.main_frame,
            type=Gtk.MessageType.QUESTION,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            message_format=text1,
        )
        dialog.set_title(_("Backup"))
        dialog.format_secondary_text(text2)
        dialog.add_buttons(
            _("Backup now"),
            BACKUP_NOW,
            _("Ask at next start"),
            ASK_NEXT_TIME,
            _("Never ask again"),
            NEVER_ASK_AGAIN,
        )

        answer = dialog.run()
        dialog.hide()
        if answer == BACKUP_NOW:
            self.backup()
        elif answer == ASK_NEXT_TIME:
            pass
        elif answer == NEVER_ASK_AGAIN:
            self.journal.config["lastBackupDate"] = datetime.datetime.max.strftime(DATE_FORMAT)

    def backup(self):
        selection = self._get_backup_file()
        # Abort if user did not select a path.
        if not selection:
            return False
        if isinstance(selection, (str, os.PathLike)):
            selection = BackupSelection(os.fspath(selection), overwrite=False)
        backup_file = selection.path

        self.journal.save_to_disk()
        data_dir = self.journal.dirs.data_dir
        archive_files = []
        for root, _directories, files in os.walk(data_dir):
            for file in files:
                if not file.endswith("~") and not any(
                    prefix in file for prefix in ("DayQuay-Backup", "Jotmorrow-Backup")
                ):
                    archive_files.append(os.path.join(root, file))

        try:
            write_archive(
                backup_file,
                archive_files,
                data_dir,
                overwrite=selection.overwrite,
                approved_identity=selection.approved_identity,
            )
        except (FileExistsError, InvalidBackupSource, OSError) as err:
            self.journal.show_message(
                _("The portable backup was not created: %s. "
                  "Your journal and the existing destination were unchanged.")
                % err,
                title=_("Backup failed"),
                error=True,
            )
            return False

        logging.info(f"The content has been backed up at {backup_file}")
        self.journal.config["lastBackupDate"] = datetime.datetime.now().strftime(DATE_FORMAT)
        self.journal.config["lastBackupDir"] = os.path.dirname(backup_file)
        return True

    def _last_backup_age(self):
        now = datetime.datetime.now()
        date_string = self.journal.config.read("lastBackupDate", now.strftime(DATE_FORMAT))
        try:
            last_backup_date = datetime.datetime.strptime(date_string, DATE_FORMAT)
        except ValueError as err:
            logging.error(f"Last backup date could not be read: {err}")
            return True
        last_backup_age = (now - last_backup_date).days
        logging.info(f"Last backup was made {last_backup_age} days ago")
        return last_backup_age

    def _get_backup_file(self):
        from gi.repository import Gtk

        if self.journal.title == "data":
            name = ""
        else:
            name = "-" + self.journal.title

        proposed_filename = f"Jotmorrow-Backup{name}-{datetime.date.today()}.zip"
        proposed_directory = self.journal.config.read("lastBackupDir", os.path.expanduser("~"))

        backup_dialog = self.journal.frame.builder.get_object("backup_dialog")
        backup_dialog.set_transient_for(self.journal.frame.main_frame)
        backup_dialog.set_do_overwrite_confirmation(False)
        backup_dialog.set_current_folder(proposed_directory)
        backup_dialog.set_current_name(proposed_filename)

        filter = Gtk.FileFilter()
        filter.set_name("Zip")
        filter.add_pattern("*.zip")
        backup_dialog.add_filter(filter)

        response = backup_dialog.run()
        backup_dialog.hide()

        if response == Gtk.ResponseType.OK:
            path = backup_dialog.get_filename()
            overwrite = False
            approved_identity = None
            if os.path.exists(path):
                try:
                    approved_identity = _capture_file_identity(path)
                except InvalidBackupSource as err:
                    self.journal.show_message(
                        _("The existing backup cannot be safely replaced: %s") % err,
                        title=_("Backup failed"),
                        error=True,
                    )
                    return None
                dialog = Gtk.MessageDialog(
                    transient_for=self.journal.frame.main_frame,
                    modal=True,
                    message_type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text=_("Replace the existing backup?"),
                )
                dialog.format_secondary_text(
                    _("This replaces the file at %s. A file that appears after this "
                      "decision will not be replaced.")
                    % path
                )
                overwrite = dialog.run() == Gtk.ResponseType.YES
                dialog.destroy()
                if not overwrite:
                    return None
            return BackupSelection(
                path=path,
                overwrite=overwrite,
                approved_identity=approved_identity,
            )
