"""Product rename keeps existing profiles and previously written backup bytes."""
import hashlib
import json
import zipfile

from rednotebook import backup, info, product, restore
from types import SimpleNamespace


def test_jotmorrow_version_and_links_keep_existing_profile_files(tmp_path):
    assert info.program_name == product.PRODUCT_NAME == "Jotmorrow"
    assert info.version == "1.0.1"
    assert info.url == "https://jotmorrow.trieflow.com"
    assert info.bug_url == "https://jotmorrow.trieflow.com/support"
    roaming = tmp_path / "Roaming"
    profile = roaming / "DayQuay"
    files = {"configuration.cfg": b"firstStart=0\n", "data/2026-09.txt": b"existing journal", "templates/work.txt": b"existing template"}
    for relative, data in files.items():
        path = profile / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    assert product.default_user_dir(app_dir=tmp_path / "Jotmorrow", home_dir=tmp_path,
        platform_name="win32", environment={"APPDATA": str(roaming)}) == profile
    assert product.default_user_dir(app_dir=tmp_path / "Jotmorrow", home_dir=tmp_path,
        platform_name="win32", environment={}) == tmp_path / "AppData/Roaming/DayQuay"
    assert product.default_user_dir(app_dir=tmp_path / "Jotmorrow", home_dir=tmp_path,
        platform_name="linux", environment={}) == tmp_path / ".dayquay"
    assert product.default_user_dir(app_dir=tmp_path / "Jotmorrow", home_dir=tmp_path,
        platform_name="win32", environment={}, portable=True) == tmp_path / "Jotmorrow/user"
    assert {relative: (profile / relative).read_bytes() for relative in files} == files
    assert not (roaming / "Jotmorrow").exists()


def test_jotmorrow_reads_an_independent_pre_rename_backup(tmp_path):
    # Literal historical format identifiers, not the current writer's constants.
    data = b"1:\n  text: A journal kept before the rename\n"
    manifest = {"format": "dayquay-backup", "version": 1, "created_at": "2026-09-11T00:00:00+00:00",
        "entries": [{"path": "2026-09.txt", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}]}
    archive = tmp_path / "DayQuay-Backup-2026-09-11.zip"
    with zipfile.ZipFile(archive, "w") as container:
        container.writestr("2026-09.txt", data)
        container.writestr("dayquay-manifest.json", json.dumps(manifest))
    before = archive.read_bytes()
    inspection = restore.inspect_backup(archive)
    destination = tmp_path / "Restored"
    restore.restore_backup(archive, destination, inspection)
    assert (destination / "2026-09.txt").read_bytes() == data
    assert archive.read_bytes() == before


def test_backup_omits_both_old_and_new_automatic_backup_names(tmp_path, monkeypatch):
    journal = tmp_path / "data"
    journal.mkdir()
    month = journal / "2026-09.txt"
    month.write_bytes(b"1:\n  text: A preserved entry\n")
    previous = {"DayQuay-Backup-2026-09-11.zip": b"old backup bytes", "Jotmorrow-Backup-2026-09-12.zip": b"new backup bytes"}
    for name, data in previous.items(): (journal / name).write_bytes(data)
    archive = tmp_path / "Jotmorrow-Backup.zip"
    app = SimpleNamespace(dirs=SimpleNamespace(data_dir=journal), config={}, save_to_disk=lambda: None)
    archiver = backup.Archiver(app)
    monkeypatch.setattr(archiver, "_get_backup_file", lambda: str(archive))
    assert archiver.backup()
    with zipfile.ZipFile(archive) as container:
        assert set(container.namelist()) == {"2026-09.txt", "dayquay-manifest.json"}
        assert container.read("2026-09.txt") == month.read_bytes()
    assert {name: (journal / name).read_bytes() for name in previous} == previous
