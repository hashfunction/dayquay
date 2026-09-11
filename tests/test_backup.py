import hashlib
import json
import os
import zipfile

import pytest
import yaml

from rednotebook import backup, restore


def valid_month(text="journal"):
    return yaml.safe_dump({1: {"text": text}}, allow_unicode=True).encode()


def test_backup_manifest_covers_exact_unicode_attachment_bytes(tmp_path):
    data = tmp_path / "journal"
    data.mkdir()
    attachment = data / "Résumé 图片.png"
    attachment.write_bytes(b"png-bytes")
    output = tmp_path / "backup.zip"

    result = backup.write_archive(output, [attachment], base_dir=data)

    with zipfile.ZipFile(output) as archive:
        archived = archive.read("Résumé 图片.png")
        manifest = json.loads(archive.read(backup.MANIFEST_NAME))
    assert archived == b"png-bytes"
    assert manifest["format"] == "dayquay-backup"
    assert manifest["version"] == 1
    assert manifest["entries"] == [
        {
            "path": "Résumé 图片.png",
            "sha256": hashlib.sha256(archived).hexdigest(),
            "size": len(archived),
        }
    ]
    assert result.file_count == 1
    assert result.total_bytes == len(archived)


def test_empty_journal_produces_manifest_only_archive(tmp_path):
    output = tmp_path / "empty.zip"

    result = backup.write_archive(output, [], base_dir=tmp_path)

    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == [backup.MANIFEST_NAME]
    assert result.file_count == 0
    assert result.total_bytes == 0


def test_backup_refuses_source_outside_journal(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"private")

    with pytest.raises(backup.InvalidBackupSource, match="outside"):
        backup.write_archive(tmp_path / "backup.zip", [outside], base_dir=journal)


def test_backup_refuses_source_symlink(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    target = journal / "target.txt"
    target.write_bytes(b"target")
    link = journal / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")

    with pytest.raises(backup.InvalidBackupSource, match="symbolic link"):
        backup.write_archive(tmp_path / "backup.zip", [link], base_dir=journal)


def test_backup_no_replace_preserves_destination_created_during_export(tmp_path, monkeypatch):
    journal = tmp_path / "journal"
    journal.mkdir()
    source = journal / "2026-09.txt"
    source.write_bytes(valid_month())
    output = tmp_path / "backup.zip"
    real_publish = backup._publish_no_replace

    def create_competing_destination(staged, destination):
        destination.write_bytes(b"competitor")
        real_publish(staged, destination)

    monkeypatch.setattr(backup, "_publish_no_replace", create_competing_destination)

    with pytest.raises(FileExistsError):
        backup.write_archive(output, [source], base_dir=journal)

    assert output.read_bytes() == b"competitor"
    assert not list(tmp_path.glob(".backup.zip.*.tmp"))


def test_backup_overwrite_requires_explicit_argument(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    source = journal / "2026-09.txt"
    new_journal = valid_month("new journal")
    source.write_bytes(new_journal)
    output = tmp_path / "backup.zip"
    output.write_bytes(b"old archive")
    approved_identity = backup._capture_file_identity(output)

    with pytest.raises(FileExistsError):
        backup.write_archive(output, [source], base_dir=journal)
    with pytest.raises(backup.InvalidBackupSource, match="selected file identity"):
        backup.write_archive(output, [source], base_dir=journal, overwrite=True)
    assert output.read_bytes() == b"old archive"
    result = backup.write_archive(
        output,
        [source],
        base_dir=journal,
        overwrite=True,
        approved_identity=approved_identity,
    )

    assert result.file_count == 1
    with zipfile.ZipFile(output) as archive:
        assert archive.read("2026-09.txt") == new_journal
    assert not list(tmp_path.glob(".backup.zip.approved-*.tmp"))


def test_backup_overwrite_never_follows_destination_symlink(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    source = journal / "2026-09.txt"
    source.write_bytes(valid_month())
    victim = tmp_path / "victim.bin"
    victim.write_bytes(b"keep me")
    output = tmp_path / "backup.zip"
    try:
        output.symlink_to(victim)
    except OSError:
        pytest.skip("symlinks unavailable")

    with pytest.raises(backup.InvalidBackupSource, match="destination.*symbolic link"):
        backup.write_archive(output, [source], base_dir=journal, overwrite=True)

    assert victim.read_bytes() == b"keep me"
    assert output.is_symlink()


def test_archive_member_names_are_sorted_and_posix(tmp_path):
    journal = tmp_path / "journal"
    nested = journal / "attachments"
    nested.mkdir(parents=True)
    later = nested / "z.txt"
    earlier = journal / "a.txt"
    later.write_bytes(b"z")
    earlier.write_bytes(b"a")
    output = tmp_path / "backup.zip"

    backup.write_archive(output, [later, earlier], base_dir=journal, arc_base_dir="journal")

    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == [
            "journal/a.txt",
            "journal/attachments/z.txt",
            backup.MANIFEST_NAME,
        ]
        assert all("\\" not in name and not name.startswith("/") for name in archive.namelist())


def test_backup_fsync_uses_writable_descriptor_for_windows_compatibility(tmp_path, monkeypatch):
    try:
        import fcntl
    except ImportError:
        pytest.skip("descriptor mode inspection requires fcntl")
    journal = tmp_path / "journal"
    journal.mkdir()
    source = journal / "2026-09.txt"
    source.write_bytes(valid_month())
    real_fsync = os.fsync
    modes = []

    def require_writable_descriptor(descriptor):
        mode = fcntl.fcntl(descriptor, fcntl.F_GETFL) & os.O_ACCMODE
        modes.append(mode)
        if mode == os.O_RDONLY:
            raise OSError(9, "Windows rejects fsync on a read-only descriptor")
        real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", require_writable_descriptor)

    backup.write_archive(tmp_path / "backup.zip", [source], base_dir=journal)

    assert modes and all(mode != os.O_RDONLY for mode in modes)


def test_archiver_does_not_authorize_destination_created_after_selection(
    tmp_path, monkeypatch
):
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    (journal_dir / "2026-09.txt").write_bytes(valid_month())
    output = tmp_path / "selected-new-name.zip"

    class Config(dict):
        def read(self, key, default=None):
            return self.get(key, default)

    class Journal:
        title = "data"
        config = Config()
        dirs = type("Dirs", (), {"data_dir": str(journal_dir)})()

        def save_to_disk(self):
            output.write_bytes(b"CREATED_BY_OTHER_PROCESS")

        def show_message(self, message, **kwargs):
            self.message = message

    journal = Journal()
    archiver = backup.Archiver(journal)
    monkeypatch.setattr(archiver, "_get_backup_file", lambda: str(output))

    result = archiver.backup()

    assert result is False
    assert output.read_bytes() == b"CREATED_BY_OTHER_PROCESS"
    assert "lastBackupDate" not in journal.config


def test_archiver_rejects_replacement_after_overwrite_approval(tmp_path, monkeypatch):
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    (journal_dir / "2026-09.txt").write_bytes(valid_month())
    output = tmp_path / "approved-existing.zip"
    output.write_bytes(b"USER_APPROVED_OLD_BACKUP")
    approved_identity = backup._capture_file_identity(output)

    class Config(dict):
        def read(self, key, default=None):
            return self.get(key, default)

    class Journal:
        title = "data"
        config = Config()
        dirs = type("Dirs", (), {"data_dir": str(journal_dir)})()

        def save_to_disk(self):
            replacement = tmp_path / "replacement.tmp"
            replacement.write_bytes(b"UNAPPROVED_REPLACEMENT")
            os.replace(replacement, output)

        def show_message(self, message, **kwargs):
            self.message = message

    journal = Journal()
    archiver = backup.Archiver(journal)
    selection = backup.BackupSelection(
        path=str(output), overwrite=True, approved_identity=approved_identity
    )
    monkeypatch.setattr(archiver, "_get_backup_file", lambda: selection)

    result = archiver.backup()

    assert result is False
    assert output.read_bytes() == b"UNAPPROVED_REPLACEMENT"
    assert "lastBackupDate" not in journal.config
    assert not list(tmp_path.glob(".approved-existing.zip.approved-*.tmp"))


def test_highly_compressible_backup_round_trips_through_default_inspector(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    month = journal / "2026-09.txt"
    month.write_bytes(valid_month("a" * 100_000))
    output = tmp_path / "portable.zip"

    backup.write_archive(output, [month], base_dir=journal)
    inspection = restore.inspect_backup(output)

    assert inspection.file_count == 1
    assert inspection.total_bytes == month.stat().st_size


def test_portable_backup_rejects_external_attachment_reference(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    external = tmp_path / "external.pdf"
    external.write_bytes(b"pdf")
    month = journal / "2026-09.txt"
    month.write_bytes(valid_month(f'[external.pdf ""file://{external}""]'))

    with pytest.raises(backup.InvalidBackupSource, match="external.*not portable"):
        backup.write_archive(tmp_path / "portable.zip", [month], base_dir=journal)
