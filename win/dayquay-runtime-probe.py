"""Qualification of real native imports; does not open or alter a user journal."""
import json
import sys
from pathlib import Path
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GtkSource
import cairo
import enchant
import yaml

buffer = GtkSource.Buffer()
buffer.set_text("DayQuay runtime qualification")
assert buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True) == "DayQuay runtime qualification"
dictionary = enchant.Dict("en_US")
assert dictionary.check("journal")
assert not dictionary.check("qzxwqzxw")
payload = {
    "status": "native_runtime_qualified_not_packaged",
    "python": sys.version,
    "gtk": [Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()],
    "cairo": cairo.cairo_version_string(),
    "pyyaml": yaml.__version__,
    "pyenchant": enchant.__version__,
    "spellcheck": "en_US correct and incorrect words verified",
    "pyinstaller": __import__("PyInstaller").__version__,
    "feature_implemented": False,
    "windows_app_built": False,
}
Path("build-evidence").mkdir(exist_ok=True)
Path("build-evidence/native-runtime.json").write_text(json.dumps(payload, indent=2)+"\n", encoding="utf-8")
print(json.dumps(payload, indent=2))
