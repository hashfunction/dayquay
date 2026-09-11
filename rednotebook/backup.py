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
        os.link(staged, destination)
    except FileExistsError:
        raise
    except OSError as exc:
        raise OSError(f'Atomic no-replace publish failed for "{destination}": {exc}') from exc
    os.unlink(staged)


def write_archive(
    archive_file_name, files, base_dir="", arc_base_dir="", *, overwrite=False
):
    """Write a portable archive and publish it after full integrity verification."""
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
        with zipfile.ZipFile(staged, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
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
        if overwrite:
            os.replace(staged, destination)
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
        backup_file = self._get_backup_file()
        # Abort if user did not select a path.
        if not backup_file:
            return

        self.journal.save_to_disk()
        data_dir = self.journal.dirs.data_dir
        archive_files = []
        for root, _, files in os.walk(data_dir):
            for file in files:
                if not file.endswith("~") and "DayQuay-Backup" not in file:
                    archive_files.append(os.path.join(root, file))

        write_archive(
            backup_file,
            archive_files,
            data_dir,
            overwrite=os.path.exists(backup_file),
        )

        logging.info(f"The content has been backed up at {backup_file}")
        self.journal.config["lastBackupDate"] = datetime.datetime.now().strftime(DATE_FORMAT)
        self.journal.config["lastBackupDir"] = os.path.dirname(backup_file)

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

        proposed_filename = f"DayQuay-Backup{name}-{datetime.date.today()}.zip"
        proposed_directory = self.journal.config.read("lastBackupDir", os.path.expanduser("~"))

        backup_dialog = self.journal.frame.builder.get_object("backup_dialog")
        backup_dialog.set_transient_for(self.journal.frame.main_frame)
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
            return path
