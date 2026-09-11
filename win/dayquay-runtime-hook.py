"""PyInstaller runtime hook: configure the bundled Enchant ABI before imports."""

import os
import sys
from pathlib import Path


base_dir = Path(sys._MEIPASS)
dll = base_dir / "libenchant-2-2.dll"
if not dll.is_file():
    raise RuntimeError(f"DayQuay package is missing its Enchant runtime: {dll}")
os.environ["PYENCHANT_LIBRARY_PATH"] = str(dll.resolve())
