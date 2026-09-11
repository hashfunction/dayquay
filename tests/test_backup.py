import hashlib
import json
import os
import zipfile

import pytest

from rednotebook import backup


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
    source.write_bytes(b"journal")
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
    source.write_bytes(b"new journal")
    output = tmp_path / "backup.zip"
    output.write_bytes(b"old archive")

    with pytest.raises(FileExistsError):
        backup.write_archive(output, [source], base_dir=journal)
    result = backup.write_archive(output, [source], base_dir=journal, overwrite=True)

    assert result.file_count == 1
    with zipfile.ZipFile(output) as archive:
        assert archive.read("2026-09.txt") == b"new journal"


def test_backup_overwrite_never_follows_destination_symlink(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    source = journal / "2026-09.txt"
    source.write_bytes(b"journal")
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
    source.write_bytes(b"journal")
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
