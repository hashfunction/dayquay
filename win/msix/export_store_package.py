"""Retain a qualified unsigned Store MSIX bound to reviewed public source."""
# Copyright 2026 Trieflow LLC. MIT.
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.request import Request, urlopen

import msix_qualification as msix
from source_publication import (MANIFEST_URL, RELEASE_TAG, REPOSITORY,
                                digest, require, validate_native_closure, validate_publication)
from store_workflow_evidence import validate_workflow

PACKAGE_NAME = "Jotmorrow_1.0.1.0_x64.msix"
PACKAGE_FULL_NAME = "1659hashfunction.DayQuay_1.0.1.0_x64__r3hxytd7jt6c4"


def read_bytes(path):
    with msix._regular_stream(path) as stream:
        value = stream.read(16 * 1024 * 1024 + 1)
    require(len(value) <= 16 * 1024 * 1024, "Oversized release evidence")
    return value


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "Jotmorrow-source-verification"}), timeout=30) as response:
        require(response.status == 200, "Public source evidence is unavailable")
        value = response.read(1024 * 1024 + 1)
    require(len(value) <= 1024 * 1024, "Public source evidence exceeds its bound")
    return value


def verify_checkout(source, commit, reviewed):
    require(re.fullmatch(r"[0-9a-f]{40}", commit or "") and reviewed == commit,
            "Export requires this exact explicitly reviewed public commit")
    def git(*args):
        return subprocess.run(["git", "-C", str(source), *args], check=True, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    require(git("rev-parse", "HEAD") == commit and not git("status", "--porcelain", "--untracked-files=all"),
            "Store export requires the unchanged committed source checkout")
    return git("show", "-s", "--format=%T", "HEAD")


def remove_owned_export(output, identity, expected):
    current = msix._reject_link(output)
    require((current.st_dev, current.st_ino) == identity, "Export directory ownership changed")
    entries = list(output.iterdir())
    require(all(path.name in expected for path in entries), "Unexpected export output is preserved")
    for path in entries:
        require(msix.file_record(path) == expected[path.name], "Changed export bytes are preserved")
    for path in entries:
        path.unlink()
    output.rmdir()


def export_store_package(package, source, output, commit, reviewed, run_id, attempt, fetcher=fetch):
    package, source, output = Path(package), Path(source).absolute(), Path(output).absolute()
    require(re.fullmatch(r"[1-9][0-9]*", run_id or "") and re.fullmatch(r"[1-9][0-9]*", attempt or ""),
            "Exact workflow run and attempt are required")
    require(not os.path.lexists(output), "Store export output already exists")
    for ancestor in (output.parent, *output.parent.parents):
        msix._reject_link(ancestor)
    tree = verify_checkout(source, commit, reviewed)
    evidence_bytes = {}
    def raw(relative):
        value = read_bytes(source / relative)
        require(relative not in evidence_bytes or evidence_bytes[relative] == value, "Release evidence changed while reading")
        evidence_bytes[relative] = value
        return value
    def load(relative):
        return json.loads(raw(relative).decode("utf-8-sig"))
    try:
        prefix = "build-evidence/msix-store-install/"
        record = load("build-evidence/msix-store-package-record.json")
        native = load("build-evidence/windows-startup.json")
        installed = load(prefix + "installation-qualification.json")
        workflow = load(prefix + "installed-consumer-workflow.json")
        for receipt in (native, installed, workflow):
            require(receipt["source_commit"] == commit and receipt["workflow_run_id"] == run_id
                    and receipt["workflow_run_attempt"] == attempt, "Receipt source/run/attempt differs")
        require(record["sourceCommit"] == commit and record["identityMode"] == "store"
                and record["identity"] == msix.STORE_IDENTITY and record["storeIdentityUsed"] is True
                and record["qualificationIdentityOnly"] is False and record["signed"] is False,
                "Only the fixed unsigned Store identity may be exported")
        require(installed["identity"] == msix.STORE_IDENTITY and installed["identity_mode"] == "store"
                and installed["qualification_identity_only"] is False and installed["store_identity_used"] is True,
                "Installed Store identity differs")
        for key in ("add_appx_completed", "registration_ownership_established", "unsigned_package_unchanged",
                    "process_identity_ownership_established", "process_shutdown_verified", "clean_close_verified",
                    "uninstall_verified", "workflow_profile_removed", "installation_qualification_passed",
                    "journal_backup_restore_workflow_tested"):
            require(installed[key] is True, "Store qualification did not pass: " + key)
        for key in ("package_full_name", "owned_package_full_name", "activated_process_package_full_name"):
            require(installed[key] == PACKAGE_FULL_NAME, "Owned Store package differs: " + key)
        for key in ("preflight_package_full_names", "residual_package_full_names", "cleanup_errors", "evidence_errors"):
            require(installed[key] == [], "Unresolved installation evidence: " + key)
        require(installed["primary_error"] is None and installed["certificate_private_key_exported"] is False
                and native["windows_native_startup"] is True, "Native startup failed or signing material was exported")
        release = source / "dist/Jotmorrow"
        msix.verify_record_inputs(package, source / "build-evidence/msix-store-package-record.json", release,
                                 source / "rednotebook/images/jotmorrow-icon/jotmorrow-256.png", commit,
                                 source / "build-evidence/package-inventory.json", source / "build-evidence/windows-startup.json", source, "store")
        payload = record["payload"]
        require(native["executable_sha256"].lower() == installed["executable_sha256"] == payload["Jotmorrow.exe"]["sha256"],
                "Startup and installed executable bytes differ")
        window = load(prefix + "window-observation.json")
        require(window == installed["window"] and window["title"] == native["window_title"] == window["expected_title"]
                and window["screenshot_captured"] is True and window["screenshot_error"] is None
                and window["screenshot_sha256"] == digest(raw(prefix + "qualification-window.png"))["sha256"],
                "Native window/screenshot provenance differs")
        modules = load(prefix + "loaded-modules.json")
        require(type(installed["loaded_module_count"]) is int and installed["loaded_module_count"] == len(modules),
                "Loaded module evidence is incomplete")
        require(isinstance(modules, list) and all(row["origin"] in
                ("package", "windows", "microsoft_defender_signed_platform") for row in modules),
                "Loaded module has an unproved origin")
        package_rows = [row for row in modules if row["origin"] == "package"]
        packaged = {row["relative_path"]: row for row in package_rows}
        require(len(packaged) == len(package_rows), "Duplicate loaded package module evidence")
        for path, row in packaged.items():
            require(path in payload and row["sha256"] == payload[path]["sha256"], "Loaded package module differs")
        require(set(record["runtime"].values()).issubset(packaged), "Required native runtimes were not observed loaded")
        validate_workflow(workflow, installed, native["window_title"], digest(raw("win/msix/installed_workflow_qualification.py"))["sha256"])
        closure = load("win/msix/native-source-publication.json")
        publication = validate_native_closure(closure, record)
        remote_manifest = fetcher(MANIFEST_URL)
        remote_release = json.loads(fetcher(f"https://api.github.com/repos/{REPOSITORY}/releases/tags/{RELEASE_TAG}"))
        validate_publication(closure, remote_manifest, remote_release)
        remote_commit = json.loads(fetcher(f"https://api.github.com/repos/{REPOSITORY}/commits/{commit}"))
        require(remote_commit["sha"] == commit and remote_commit["commit"]["tree"]["sha"] == tree,
                "Reviewed application source tree is not publicly available at the exact commit")
        container = msix.verify_msix(package, payload, "store")
        require(container == record["containerVerification"] and container["package"]["sha256"] == installed["unsigned_package_sha256"],
                "Unsigned package differs from the installed qualification input")
        def unchanged():
            require(verify_checkout(source, commit, reviewed) == tree, "Reviewed source tree changed during export")
            for path, value in evidence_bytes.items():
                require(read_bytes(source / path) == value, "Retained qualification evidence changed during export")
            msix.verify_record_inputs(package, source / "build-evidence/msix-store-package-record.json", release,
                                     source / "rednotebook/images/jotmorrow-icon/jotmorrow-256.png", commit,
                                     source / "build-evidence/package-inventory.json", source / "build-evidence/windows-startup.json", source, "store")
        unchanged()
        ready = {"schema_version": 1, "unsigned_store_package_ready": True, "submitted": False,
                 "public_application_binary_released": False, "store_certification_claimed": False,
                 "source_commit": commit, "reviewed_public_source": reviewed, "source_tree": tree,
                 "workflow_run_id": run_id, "workflow_run_attempt": attempt,
                 "generated_at_utc": datetime.now(timezone.utc).isoformat(), "identity": msix.STORE_IDENTITY,
                 "unsigned_package": dict(container["package"], name=PACKAGE_NAME), "native_source_publication": publication,
                 "public_source_responses": {"manifest": digest(remote_manifest), "release": remote_release["id"], "commit": remote_commit["sha"]},
                 "evidence": {name: digest(data) for name, data in evidence_bytes.items()}}
        output.mkdir()
        created = msix._reject_link(output)
        identity = (created.st_dev, created.st_ino)
        ready_bytes = msix._canonical_json(ready)
        try:
            with msix._regular_stream(package) as incoming, (output / PACKAGE_NAME).open("xb") as target:
                shutil.copyfileobj(incoming, target, 1024 * 1024)
            require(msix.verify_msix(output / PACKAGE_NAME, payload, "store") == container, "Retained unsigned package changed")
            unchanged()
            msix._write_new(output / "release-ready.json", ready_bytes)
        except Exception as error:
            try:
                remove_owned_export(output, identity, {PACKAGE_NAME: container["package"], "release-ready.json": digest(ready_bytes)})
            except (OSError, ValueError) as cleanup_error:
                raise ValueError(f"Store export failed; changed/unexpected output preserved: {cleanup_error}") from error
            raise
        return ready
    except (KeyError, TypeError, AttributeError, OSError, json.JSONDecodeError) as error:
        raise ValueError("Incomplete Store export evidence") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("package", "source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--reviewed-public-source", required=True)
    args = parser.parse_args()
    require(sys.platform == "win32" and os.environ.get("CI") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch",
            "Store export requires the explicitly dispatched disposable Windows workflow")
    export_store_package(args.package, args.source, args.output, os.environ.get("GITHUB_SHA"), args.reviewed_public_source,
                         os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT"))
    print("PASS: reviewed public source, native closure, full installed workflow and cleanup bind the retained unsigned Store package")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Store export refused: " + str(error), file=sys.stderr)
        sys.exit(1)
