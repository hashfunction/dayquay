"""Preserve installed native notices and record the exact Jotmorrow stage.
Copyright 2026 Trieflow LLC. MIT; packaging helper only, not a license clearance.
"""

import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "msix"))
from msix_qualification import (
    create_input_inventory,
    file_record,
    inventory_tree,
    _regular_stream,
    _write_new,
    _canonical_json,
    notice_supplement_inventory,
)


def collect_notices(prefix, release, supplement=None):
    source = Path(prefix) / "share/licenses"
    measured = inventory_tree(source)
    supplement = (
        Path(supplement) if supplement is not None else Path(__file__).parent / "notice-supplement"
    )
    originals = notice_supplement_inventory(supplement)
    output = Path(release) / "_internal/notices"
    if os.path.lexists(output):
        raise ValueError("Native notice output already exists and will not be replaced")
    output.mkdir(parents=True)
    try:
        for relative in measured:
            target = output / "native" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with _regular_stream(source / relative) as stream, target.open("xb") as destination:
                shutil.copyfileobj(stream, destination)
        if inventory_tree(source) != measured or inventory_tree(output / "native") != measured:
            raise ValueError("Native notice source changed while copying")
        for relative in originals:
            target = output / "supplement" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with _regular_stream(supplement / relative) as stream, target.open("xb") as destination:
                shutil.copyfileobj(stream, destination)
        if (
            notice_supplement_inventory(supplement) != originals
            or inventory_tree(output / "supplement") != originals
        ):
            raise ValueError("Original notice supplement changed while copying")
        return dict(
            files=inventory_tree(output),
            inventoryIsLicenseClearance=False,
            unresolved=[
                "Complete direct/transitive native binary, license and corresponding-source audit required",
                "Collected installed notices do not prove source delivery or complete dependency notice coverage",
            ],
        )
    except Exception:
        shutil.rmtree(output)
        raise


def main():
    if os.name != "nt" or os.environ.get("CI") != "true":
        raise SystemExit("Requires the same disposable Windows MSYS2 build environment")
    source = Path(__file__).resolve().parents[1]
    commit = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if commit != os.environ.get("GITHUB_SHA"):
        raise SystemExit("Source differs from this native build")
    release = source / "dist/Jotmorrow"
    evidence = source / "build-evidence"
    notices = collect_notices(Path(sys.prefix), release)
    # PyEnchant is installed separately from pacman. Preserve available installed
    # distribution license files as well, with an explicit gate if absent.
    distribution = importlib.metadata.distribution("pyenchant")
    notice_files = [
        path
        for path in (distribution.files or [])
        if any(
            part.lower() in ("licenses", "license", "copying", "license.txt", "copying.txt")
            for part in path.parts
        )
    ]
    if not notice_files:
        notices["unresolved"].append(
            "Installed PyEnchant distribution notice absent; source-license delivery required"
        )
    for relative in notice_files:
        actual = Path(distribution.locate_file(relative))
        # Only metadata-owned notice paths, no arbitrary distribution file copying.
        if ".." in relative.parts or relative.is_absolute():
            raise ValueError("Unsafe PyEnchant notice path")
        target = release / "_internal/notices/pyenchant" / str(relative)
        with _regular_stream(actual) as stream:
            _write_new(target, stream.read())
        if file_record(actual) != file_record(target):
            raise ValueError("PyEnchant notice changed while copying")
    notices["files"] = inventory_tree(release / "_internal/notices")
    _write_new(evidence / "native-notices.json", _canonical_json(notices))
    python = Path(sys.executable).resolve()
    _write_new(
        evidence / "packaging-python.json",
        _canonical_json(
            dict(
                path=str(python),
                **file_record(python),
                version=sys.version,
                prefix=str(Path(sys.prefix).resolve()),
            )
        ),
    )
    inventory = create_input_inventory(release, source, commit)
    _write_new(evidence / "package-inventory.json", _canonical_json(inventory))
    print(
        f"Recorded {len(inventory['files'])} exact stage files; native license/source clearance remains false"
    )


if __name__ == "__main__":
    main()
