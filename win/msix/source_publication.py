"""Bind unchanged native inputs and notices to their published source collection."""
# Copyright 2026 Trieflow LLC. MIT.
import hashlib
import json
from pathlib import PurePosixPath

REPOSITORY = "hashfunction/dayquay"
RELEASE_TAG = "native-sources-2026-09-11-df058"
RELEASE_URL = f"https://github.com/{REPOSITORY}/releases/tag/{RELEASE_TAG}"
DOWNLOAD_URL = f"https://github.com/{REPOSITORY}/releases/download/{RELEASE_TAG}/"
MANIFEST_URL = DOWNLOAD_URL + "source-manifest.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def validate_native_closure(closure, record):
    try:
        require(closure["schema_version"] == 1 and closure["source_release"] == RELEASE_URL,
                "Unreviewed native source publication")
        checks = closure["audit_checks"]
        require(set(checks) == {"public_release_asset_digests_match", "source_archive_and_all_members_verified",
                "all_native_archives_unchanged", "all_native_versions_unchanged", "all_mapped_vendor_payload_unchanged",
                "all_original_notices_match", "all_source_inputs_match"} and all(v is True for v in checks.values()),
                "Native source audit is incomplete")
        application = closure["current_application"]
        require(application["name"] == "Jotmorrow" and application["version"] == "1.0.1"
                and application["msix_version"] == record["identity"]["version"] == "1.0.1.0"
                and record["identity"]["executable"] == "Jotmorrow.exe"
                and application["source_page"] == "https://jotmorrow.trieflow.com/source",
                "Current renamed application/source identity differs")
        current_inputs = {path: value for path, value in record["sourceInputs"].items()
                          if not path.startswith("win/notice-supplement/")}
        require(bool(application["source_inputs"]) and current_inputs == application["source_inputs"],
                "Current application source differs from reviewed rename binding")
        native = record["buildProvenance"]["nativeInputs"]
        require(native["archives"] == closure["native_archives"], "Native archive inputs differ from published-source audit")
        require(native["installedVersions"] == closure["installed_native_versions"], "Native versions differ from published-source audit")
        for group in ("vendor_payload", "original_notice_payload"):
            require(bool(closure[group]), "Empty reviewed native payload boundary")
            for path, expected in closure[group].items():
                require(record["releaseInput"].get(path) == expected, f"Native source/notice payload changed: {path}")
        for path in record["releaseInput"]:
            suffix = PurePosixPath(path).suffix.lower()
            if suffix in (".dll", ".pyd", ".exe") and path != record["identity"]["executable"]:
                require(path in closure["vendor_payload"], f"Native executable has no reviewed source owner: {path}")
        require(record["sourceInputs"]["win/notice-supplement/index.json"] == closure["notice_supplement_index"],
                "Original notice index differs from reviewed source collection")
        return {"source_release": RELEASE_URL, "source_manifest": closure["source_manifest"],
                "application": {"name": application["name"], "version": application["version"],
                                "source_page": application["source_page"], "bound_source_inputs": len(current_inputs)},
                "source_archive": closure["source_archive"], "native_archives": len(native["archives"]),
                "native_versions": len(native["installedVersions"]), "mapped_vendor_files": len(closure["vendor_payload"]),
                "original_notice_files": len(closure["original_notice_payload"]), "vendor_binary_reproduction_claimed": False}
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Incomplete native source closure evidence") from error


def validate_publication(closure, manifest_bytes, release_metadata):
    try:
        expected = closure["source_manifest"]
        require(digest(manifest_bytes) == {k: expected[k] for k in ("bytes", "sha256")}, "Published source manifest changed")
        manifest = json.loads(manifest_bytes)
        require(len(manifest["archives"]) == closure["source_archive_inputs"] and
                len(manifest["archives"]) + len(manifest["metadata"]) + 1 == closure["source_archive_members"],
                "Published source collection membership differs")
        require(release_metadata["draft"] is False and release_metadata["tag_name"] == RELEASE_TAG,
                "Source release is not publicly available")
        for asset in (closure["source_manifest"], closure["source_archive"]):
            found = [a for a in release_metadata["assets"] if a["name"] == asset["name"]]
            require(len(found) == 1 and found[0]["size"] == asset["bytes"] and
                    found[0]["digest"] == "sha256:" + asset["sha256"] and
                    found[0]["browser_download_url"] == DOWNLOAD_URL + asset["name"],
                    "Published source asset differs from audited bytes")
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as error:
        raise ValueError("Incomplete public source delivery evidence") from error
