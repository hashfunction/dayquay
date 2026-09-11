import hashlib
import json
import os
import stat
import zipfile

import pytest
import yaml

from rednotebook import backup, restore, storage


def make_backup(tmp_path, files, *, declared=None, name="backup.zip"):
    path = tmp_path / name
    declared = files if declared is None else declared
    entries = [
        {
            "path": member,
            "sha256": hashlib.sha256(declared[member]).hexdigest(),
            "size": len(declared[member]),
        }
        for member in sorted(declared)
    ]
    manifest = {
        "created_at": "2026-09-11T00:00:00+00:00",
        "entries": entries,
        "format": "dayquay-backup",
        "version": 1,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for member, content in files.items():
            archive.writestr(member, content)
        archive.writestr(backup.MANIFEST_NAME, json.dumps(manifest))
    return path


@pytest.mark.parametrize("member", ["../outside.txt", "/absolute.txt", "C:/drive.txt", "a\\b"])
def test_inspection_rejects_escape_and_windows_alias_paths(tmp_path, member):
    archive = make_backup(tmp_path, {member: b"x"})

    with pytest.raises(restore.InvalidBackup, match="unsafe path"):
        restore.inspect_backup(archive)


@pytest.mark.parametrize(
    "member", ["name:stream", "folder/file.", "folder/file ", "CON", "aux.txt", "a//b"]
)
def test_inspection_rejects_windows_device_and_noncanonical_paths(tmp_path, member):
    archive = make_backup(tmp_path, {member: b"x"})

    with pytest.raises(restore.InvalidBackup, match="unsafe path"):
        restore.inspect_backup(archive)


def test_inspection_rejects_case_colliding_members(tmp_path):
    archive = make_backup(tmp_path, {"Photo.png": b"one", "photo.PNG": b"two"})

    with pytest.raises(restore.InvalidBackup, match="duplicate"):
        restore.inspect_backup(archive)


def test_inspection_rejects_symlink_member(tmp_path):
    archive_path = tmp_path / "symlink.zip"
    manifest = {
        "created_at": "2026-09-11T00:00:00+00:00",
        "entries": [
            {
                "path": "link",
                "sha256": hashlib.sha256(b"target").hexdigest(),
                "size": 6,
            }
        ],
        "format": "dayquay-backup",
        "version": 1,
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, b"target")
        archive.writestr(backup.MANIFEST_NAME, json.dumps(manifest))

    with pytest.raises(restore.InvalidBackup, match="link"):
        restore.inspect_backup(archive_path)


def test_checksum_failure_keeps_destination_absent(tmp_path):
    archive = make_backup(
        tmp_path,
        files={"2026-09.txt": b"tampered"},
        declared={"2026-09.txt": b"original"},
    )
    inspection = restore.inspect_backup(archive, verify_hashes=False)
    destination = tmp_path / "restored"

    with pytest.raises(restore.InvalidBackup, match="checksum"):
        restore.restore_backup(archive, destination, inspection)

    assert not destination.exists()
    assert not list(tmp_path.glob(".restored.dayquay-*"))


def test_restore_revalidates_archive_selected_during_inspection(tmp_path):
    first = yaml.safe_dump({1: {"text": "first"}}).encode()
    second = yaml.safe_dump({1: {"text": "second"}}).encode()
    archive = make_backup(tmp_path, {"2026-09.txt": first})
    inspection = restore.inspect_backup(archive)
    make_backup(tmp_path, {"2026-09.txt": second})

    with pytest.raises(restore.InvalidBackup, match="changed since inspection"):
        restore.restore_backup(archive, tmp_path / "restored", inspection)


def test_successful_restore_verifies_month_and_unicode_attachment(tmp_path):
    month = yaml.safe_dump({1: {"text": "Hello #journal"}}, allow_unicode=True).encode()
    archive = make_backup(
        tmp_path,
        {"2026-09.txt": month, "attachments/Résumé 图片.png": b"png"},
    )
    inspection = restore.inspect_backup(archive)
    destination = tmp_path / "restored"

    result = restore.restore_backup(archive, destination, inspection)

    assert result.file_count == 2
    assert result.total_bytes == len(month) + 3
    assert (destination / "2026-09.txt").read_bytes() == month
    assert (destination / "attachments/Résumé 图片.png").read_bytes() == b"png"
    assert result.journal.month_count == 1


def test_destination_created_during_restore_is_preserved(tmp_path, monkeypatch):
    month = yaml.safe_dump({1: {"text": "Hello"}}).encode()
    archive = make_backup(tmp_path, {"2026-09.txt": month})
    inspection = restore.inspect_backup(archive)
    destination = tmp_path / "restored"
    real_rename = restore._atomic_rename_directory_no_replace

    def create_competing_directory(source, target):
        target.mkdir()
        (target / "owner.txt").write_text("competitor", encoding="utf-8")
        real_rename(source, target)

    monkeypatch.setattr(restore, "_atomic_rename_directory_no_replace", create_competing_directory)

    with pytest.raises(FileExistsError):
        restore.restore_backup(archive, destination, inspection)

    assert (destination / "owner.txt").read_text(encoding="utf-8") == "competitor"
    assert not list(tmp_path.glob(".restored.dayquay-*"))


def test_safe_month_loader_rejects_python_object_tag_without_execution(tmp_path):
    marker = tmp_path / "executed"
    payload = f'!!python/object/apply:os.system ["touch {marker}"]\n'
    month = tmp_path / "2026-09.txt"
    month.write_text(payload, encoding="utf-8")

    with pytest.raises(storage.InvalidJournalData, match="YAML"):
        storage.load_month_from_disk(month, 2026, 9)

    assert not marker.exists()


def test_safe_month_loader_rejects_aliases_and_invalid_day_schema(tmp_path):
    alias_month = tmp_path / "2026-09.txt"
    alias_month.write_text("1: &day\n  text: hello\n2: *day\n", encoding="utf-8")
    with pytest.raises(storage.InvalidJournalData, match="aliases"):
        storage.load_month_from_disk(alias_month, 2026, 9)

    invalid_day = tmp_path / "2026-10.txt"
    invalid_day.write_text("32:\n  text: hello\n", encoding="utf-8")
    with pytest.raises(storage.InvalidJournalData, match="day number"):
        storage.load_month_from_disk(invalid_day, 2026, 10)


def test_safe_month_loader_rejects_duplicate_mapping_keys(tmp_path):
    month = tmp_path / "2026-09.txt"
    month.write_text("1:\n  text: first\n  text: replaced\n", encoding="utf-8")

    with pytest.raises(storage.InvalidJournalData, match="duplicate"):
        storage.load_month_from_disk(month, 2026, 9)


def test_inspection_enforces_compression_and_total_size_limits(tmp_path):
    archive = make_backup(tmp_path, {"attachment.bin": b"A" * 10_000})

    with pytest.raises(restore.InvalidBackup, match="compression ratio"):
        restore.inspect_backup(
            archive,
            limits=restore.RestoreLimits(max_compression_ratio=2.0),
        )
    with pytest.raises(restore.InvalidBackup, match="total uncompressed"):
        restore.inspect_backup(
            archive,
            limits=restore.RestoreLimits(
                max_total_bytes=100,
                max_compression_ratio=1_000.0,
            ),
        )


def test_month_loader_bounds_bytes_and_nesting(tmp_path):
    month = tmp_path / "2026-09.txt"
    month.write_text("1:\n  text: hello\n", encoding="utf-8")
    with pytest.raises(storage.InvalidJournalData, match="byte limit"):
        storage.load_month_from_disk(month, 2026, 9, max_bytes=4)

    nested = "leaf"
    for index in range(storage.MAX_CATEGORY_DEPTH + 1):
        nested = {f"level-{index}": nested}
    month.write_text(yaml.safe_dump({1: {"text": "hello", "deep": nested}}), encoding="utf-8")
    with pytest.raises(storage.InvalidJournalData, match="nesting"):
        storage.load_month_from_disk(month, 2026, 9)


def test_validation_rejects_external_reference_created_by_insert_file(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    external = tmp_path / "external.pdf"
    external.write_bytes(b"pdf")
    text = f'[external.pdf ""file://{external}""]'
    (journal / "2026-09.txt").write_text(
        yaml.safe_dump({1: {"text": text}}), encoding="utf-8"
    )

    with pytest.raises(restore.InvalidBackup, match="external.*not portable"):
        restore.validate_journal_directory(journal)


def test_validation_rejects_missing_relative_attachment(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    text = '[missing.pdf ""attachments/missing.pdf""]'
    (journal / "2026-09.txt").write_text(
        yaml.safe_dump({1: {"text": text}}), encoding="utf-8"
    )

    with pytest.raises(restore.InvalidBackup, match="referenced attachment is missing"):
        restore.validate_journal_directory(journal)


def test_validation_counts_existing_referenced_attachment(tmp_path):
    journal = tmp_path / "journal"
    attachment = journal / "attachments" / "report.pdf"
    attachment.parent.mkdir(parents=True)
    attachment.write_bytes(b"pdf")
    text = '[report.pdf ""attachments/report.pdf""]'
    (journal / "2026-09.txt").write_text(
        yaml.safe_dump({1: {"text": text}}), encoding="utf-8"
    )

    validation = restore.validate_journal_directory(journal)

    assert validation.attachment_count == 1
    assert validation.referenced_attachment_count == 1
