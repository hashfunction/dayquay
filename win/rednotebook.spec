# -*- mode: python ; coding: utf-8 -*-
"""Reproducible one-directory DayQuay build from an MSYS2 UCRT64 prefix."""

import os
import sys
from pathlib import Path


win_dir = Path(SPECPATH).resolve()
repo = win_dir.parent
srcdir = repo / "rednotebook"
icon = win_dir / "dayquay.ico"
prefix_value = os.environ.get("MINGW_PREFIX")
if not prefix_value:
    raise RuntimeError("MINGW_PREFIX must identify the qualified MSYS2 UCRT64 environment")
prefix = Path(prefix_value)

sys.path.insert(0, str(win_dir))
from build_support import resolve_enchant_inputs


enchant = resolve_enchant_inputs(prefix)
required = (repo, srcdir, icon, win_dir / "dayquay-runtime-hook.py")
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise RuntimeError("Missing DayQuay build inputs: " + ", ".join(missing))

datas = [(str(path), destination) for path, destination in enchant.datas]
datas.extend(
    [
        (str(srcdir / "files"), "files"),
        (str(srcdir / "images"), "images"),
        (str(repo / "LICENSE"), "."),
        (str(repo / "LICENSES"), "LICENSES"),
        (str(repo / "debian" / "copyright"), "."),
        (str(win_dir / "THIRD-PARTY-NOTICES.txt"), "."),
        (str(win_dir / "windows-dependencies.json"), "."),
    ]
)

a = Analysis(
    [str(srcdir / "journal.py")],
    pathex=[str(repo)],
    binaries=[(str(path), destination) for path, destination in enchant.binaries],
    datas=datas,
    hiddenimports=[],
    hookspath=[str(win_dir / "hooks")],
    hooksconfig={
        "gi": {
            "icons": ["Adwaita"],
            "themes": ["Adwaita"],
            "languages": ["en"],
            "module-versions": {"Gtk": "3.0", "GtkSource": "4"},
        }
    },
    runtime_hooks=[str(win_dir / "dayquay-runtime-hook.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DayQuay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="DayQuay",
)
