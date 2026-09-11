"""PyInstaller runtime hook: configure the bundled Enchant ABI before imports."""

import os
import sys
from pathlib import Path

from rednotebook import product


# The isolated qualification runner requests early boot diagnostics before GTK
# and application logging initialize. Ordinary product launches do not do this.
if os.environ.get("CI") == "true" and os.environ.get("DAYQUAY_CI_LOG"):
    diagnostic_stream = open(os.environ["DAYQUAY_CI_LOG"], "w", encoding="utf-8", buffering=1)
    sys.stdout = diagnostic_stream
    sys.stderr = diagnostic_stream

base_dir = Path(sys._MEIPASS)
product.configure_bundled_enchant(base_dir, frozen=True)
