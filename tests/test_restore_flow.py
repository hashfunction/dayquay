import hashlib
import json
import types
import zipfile

import pytest
import yaml

from rednotebook import backup
from rednotebook.gui.restore import (
    RestoreController,
    format_inspection_summary,
    resolve_new_destination,
)


class FakeConfig(dict):
    def read(self, key, default=None):
        return self.get(key, default)


class FakeJournal:
    def __init__(self, data_dir):
        self.dirs = types.SimpleNamespace(data_dir=str(data_dir))
        self.config = FakeConfig(dataDir=str(data_dir))
        self.messages = []
        self.opened = []

    def show_message(self, message, **kwargs):
        self.messages.append((message, kwargs))

    def open_restored_journal(self, path):
        self.opened.append(path)
        self.dirs.data_dir = path
        self.config["dataDir"] = path
        return True


def make_backup(tmp_path, content=None):
    content = content or yaml.safe_dump({1: {"text": "restored"}}).encode()
    member = "2026-09.txt"
    manifest = {
        "created_at": "2026-09-11T00:00:00+00:00",
        "entries": [
            {
                "path": member,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        ],
        "format": "dayquay-backup",
        "version": 1,
    }
    path = tmp_path / "journal.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, content)
        archive.writestr(backup.MANIFEST_NAME, json.dumps(manifest))
    return path


def test_failed_restore_does_not_switch_active_journal(tmp_path):
    active = tmp_path / "active"
    active.mkdir()
    journal = FakeJournal(active)
    archive = make_backup(tmp_path)
    inspection = RestoreController(journal).inspect(archive)
    with zipfile.ZipFile(archive, "a") as changed:
        changed.comment = b"changed after inspection"
    controller = RestoreController(journal)

    assert controller.restore(archive, tmp_path / "new", inspection) is None
    assert journal.dirs.data_dir == str(active)
    assert journal.config.read("dataDir") == str(active)
    assert "active journal was not changed" in journal.messages[-1][0]


def test_successful_restore_waits_for_explicit_open(tmp_path):
    active = tmp_path / "active"
    active.mkdir()
    journal = FakeJournal(active)
    archive = make_backup(tmp_path)
    controller = RestoreController(journal)
    inspection = controller.inspect(archive)
    destination = tmp_path / "restored"

    result = controller.restore(archive, destination, inspection)

    assert result.destination == str(destination)
    assert journal.dirs.data_dir == str(active)
    assert journal.opened == []
    assert controller.open_restored(result) is True
    assert journal.opened == [str(destination)]


@pytest.mark.parametrize("name", ["", ".", "..", "child/name", "child\\name", "C:drive"])
def test_destination_name_must_be_one_new_folder(tmp_path, name):
    with pytest.raises(ValueError):
        resolve_new_destination(tmp_path, name)


def test_destination_must_not_exist(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(FileExistsError):
        resolve_new_destination(tmp_path, "existing")
    assert resolve_new_destination(tmp_path, "new journal") == tmp_path / "new journal"


def test_inspection_summary_exposes_archive_facts(tmp_path):
    journal = FakeJournal(tmp_path / "active")
    inspection = RestoreController(journal).inspect(make_backup(tmp_path))

    summary = format_inspection_summary(inspection)

    assert "2026-09-11T00:00:00+00:00" in summary
    assert "1 file" in summary
    assert f"{inspection.total_bytes} bytes" in summary
