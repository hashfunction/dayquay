"""Cross-check the real installed journal/backup/restore receipt before export."""
# Copyright 2026 Trieflow LLC. MIT.
import ntpath
from pathlib import PureWindowsPath
import re

from source_publication import require
from installed_workflow_qualification import restored_window_title


def windows_path(value):
    require(isinstance(value, str) and re.match(r"^[A-Za-z]:[\\/]", value)
            and ".." not in PureWindowsPath(value).parts, "Invalid absolute workflow path")
    return ntpath.normcase(ntpath.normpath(value))


def sha(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value)


def file_set(value):
    require(isinstance(value, dict) and len(value) == 1, "Workflow month file set differs")
    for name, record in value.items():
        require(re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])\.txt", name) and
                set(record) == {"bytes", "sha256"} and type(record["bytes"]) is int and
                0 < record["bytes"] <= 1024 * 1024 and sha(record["sha256"]), "Invalid workflow month digest")


def validate_workflow(workflow, installed, title, helper_sha256):
    try:
        require(type(workflow["schema_version"]) is int and workflow["schema_version"] == 1
                and workflow["journal_backup_restore_workflow_tested"] is True
                and workflow["input_method"] == "owned Win32 SendInput keyboard/mouse"
                and workflow["helper_sha256"] == helper_sha256, "Installed workflow/helper is incomplete")
        pid, hwnd = workflow["process_id"], workflow["main_window_handle"]
        require(type(pid) is int and pid > 0 and type(hwnd) is int and hwnd > 0
                and pid == installed["window"]["process_id"] == installed["process_exit"]["process_id"]
                and hwnd == installed["window"]["main_window_handle"],
                "Workflow does not belong to the retained consumer process/window")
        for key in ("process_exit", "cleanup_process_exit"):
            exit_record = installed[key]
            require(exit_record["process_id"] == pid and exit_record["wait_completed"] is True and
                    exit_record["normal_exit"] is True and type(exit_record["exit_code"]) is int and
                    exit_record["exit_code"] == 0 and exit_record["observation_error"] is None,
                    "Normal consumer stop was not proved")
        saved, reopened = workflow["saved"], workflow["reopened"]
        sentinel = workflow["sentinel_sha256"]
        require(sha(sentinel) and saved["sentinel_sha256"] == sentinel and saved["additional_text_sha256"] == [],
                "Original saved journal marker differs")
        journal = windows_path(saved["journal_root"])
        require(PureWindowsPath(journal).name == "data" and windows_path(reopened["journal_root"]) == journal,
                "Reopened journal path differs")
        file_set(saved["files"]); file_set(reopened["files"])
        require(set(saved["files"]) == set(reopened["files"]) and saved["files"] != reopened["files"],
                "Journal reopening did not preserve the month and append independently verified content")
        name = next(iter(saved["files"]))
        require(reopened["files"][name]["bytes"] > saved["files"][name]["bytes"] and
                reopened["sentinel_sha256"] == sentinel and len(reopened["additional_text_sha256"]) == 1 and
                sha(reopened["additional_text_sha256"][0]) and reopened["additional_text_sha256"][0] != sentinel,
                "Post-reopen marker is missing or unchanged")
        require(workflow["reopen_transition"] == {"away_title": restored_window_title(title, "ReopenProbe"),
                "return_title": title}, "Observed journal transition differs")
        restored = workflow["restored"]
        require(windows_path(restored["journal_root"]) == windows_path(str(PureWindowsPath(journal).parent / "RestoredQualification"))
                and workflow["restored_window_title"] == restored_window_title(title, "RestoredQualification"),
                "Restored destination differs from the fresh owned journal")
        for item in (restored, workflow["original_after_restore"]):
            require(item["files"] == reopened["files"] and item["sentinel_sha256"] == sentinel and
                    item["additional_text_sha256"] == reopened["additional_text_sha256"],
                    "Restore changed the original or restored journal bytes")
        require(windows_path(workflow["original_after_restore"]["journal_root"]) == journal, "Protected original path differs")
        backup = workflow["backup"]
        archive = PureWindowsPath(windows_path(backup["archive"]))
        require(archive.name == "jotmorrow-consumer-backup.zip" and
                re.fullmatch(r"\.dayquay-install-[0-9a-f]{32}", archive.parent.name), "Backup escaped the owned temporary directory")
        require(type(backup["archive_bytes"]) is int and 0 < backup["archive_bytes"] <= 16 * 1024 * 1024 and
                sha(backup["archive_sha256"]) and backup["manifest_verified"] is True and
                backup["files"] == reopened["files"] and workflow["backup_after_restore"] == backup,
                "Backup manifest, original ZIP bytes or restored file set differs")
        require(installed["installed_consumer_workflow"] == workflow, "Standalone and final consumer receipts differ")
    except (KeyError, TypeError, AttributeError, StopIteration) as error:
        raise ValueError("Incomplete installed consumer workflow evidence") from error
