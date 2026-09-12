"""Recheck same-run source/stage/receipt/package binding before any install mutation.
Copyright 2026 Trieflow LLC. MIT.
"""

import argparse
from pathlib import Path
import subprocess
import sys

from msix_qualification import verify_record_inputs, verify_installed, _load_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--record", type=Path, required=True)
parser.add_argument("--package", type=Path, required=True)
parser.add_argument("--source-commit", required=True)
parser.add_argument("--installed-root", type=Path)
parser.add_argument("--identity-mode", choices=("qualification", "store"), default="qualification")
args = parser.parse_args()
source = Path(__file__).resolve().parents[2]
actual = subprocess.run(
    ["git", "-C", str(source), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
).stdout.strip()
if actual != args.source_commit:
    raise SystemExit("Source commit differs from this installation qualification run")
dirty = subprocess.run(
    ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all"],
    check=True,
    capture_output=True,
    text=True,
).stdout.strip()
if dirty:
    raise SystemExit("Dirty source checkout cannot identify qualification inputs")
from msix_qualification import file_record

python = _load_json(
    source / "build-evidence/packaging-python.json", "same-run packaging interpreter"
)
if Path(python["path"]).resolve() != Path(sys.executable).resolve() or file_record(
    sys.executable
) != {key: python[key] for key in ("bytes", "sha256")}:
    raise SystemExit("Verifier is not running in the exact recorded MSYS2 Python executable")
verify_record_inputs(
    args.package,
    args.record,
    source / "dist/Jotmorrow",
    source / "rednotebook/images/jotmorrow-icon/jotmorrow-256.png",
    actual,
    source / "build-evidence/package-inventory.json",
    source / "build-evidence/windows-startup.json",
    source,
    args.identity_mode,
)
if args.installed_root:
    verify_installed(
        args.installed_root, _load_json(args.record, "qualification record")["payload"], args.identity_mode
    )
print("PASS: exact source/stage/notices/startup/package binding reverified before installation")
