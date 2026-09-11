import importlib.util
import sys
import types
from pathlib import Path

import pytest

from win import build_support


def test_resolve_enchant_inputs_requires_runtime_provider_and_dictionary(tmp_path):
    prefix = tmp_path / "ucrt64"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "lib" / "enchant-2").mkdir(parents=True)
    (prefix / "share" / "hunspell").mkdir(parents=True)
    (prefix / "share" / "licenses" / "hunspell-en").mkdir(parents=True)
    (prefix / "bin" / "libenchant-2-2.dll").write_bytes(b"broker")
    (prefix / "lib" / "enchant-2" / "enchant_hunspell.dll").write_bytes(b"provider")
    (prefix / "share" / "hunspell" / "en_US.aff").write_text("aff", encoding="utf-8")
    (prefix / "share" / "hunspell" / "en_US.dic").write_text("dic", encoding="utf-8")
    license_file = prefix / "share" / "licenses" / "hunspell-en" / "Copyright_en_US"
    license_file.write_text("SCOWL license", encoding="utf-8")

    inputs = build_support.resolve_enchant_inputs(prefix)

    assert inputs.binaries == (
        (prefix / "bin" / "libenchant-2-2.dll", "."),
        (prefix / "lib" / "enchant-2" / "enchant_hunspell.dll", "lib/enchant-2"),
    )
    assert inputs.datas == (
        (prefix / "share" / "hunspell" / "en_US.aff", "share/hunspell"),
        (prefix / "share" / "hunspell" / "en_US.dic", "share/hunspell"),
        (license_file, "LICENSES"),
    )


def test_resolve_enchant_inputs_fails_closed_without_dictionary(tmp_path):
    prefix = tmp_path / "ucrt64"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "lib" / "enchant-2").mkdir(parents=True)
    (prefix / "bin" / "libenchant-2-2.dll").write_bytes(b"broker")
    (prefix / "lib" / "enchant-2" / "enchant_hunspell.dll").write_bytes(b"provider")

    with pytest.raises(build_support.MissingWindowsInput, match="en_US"):
        build_support.resolve_enchant_inputs(prefix)


def test_local_gtksource_hook_collects_version_four_resources(monkeypatch):
    calls = []

    class FakeModuleInfo:
        def __init__(self, name, version, hook_api=None):
            calls.append((name, version, hook_api))
            self.available = True
            self.version = version

        def collect_typelib_data(self):
            return (["binary"], ["typelib"], ["hidden"])

    fake_gi = types.ModuleType("PyInstaller.utils.hooks.gi")
    fake_gi.GiModuleInfo = FakeModuleInfo
    fake_gi.collect_glib_share_files = lambda path: [(f"source/{path}", f"share/{path}")]
    monkeypatch.setitem(sys.modules, "PyInstaller", types.ModuleType("PyInstaller"))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils", types.ModuleType("PyInstaller.utils"))
    monkeypatch.setitem(
        sys.modules, "PyInstaller.utils.hooks", types.ModuleType("PyInstaller.utils.hooks")
    )
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks.gi", fake_gi)

    hook_path = Path(__file__).parents[1] / "win" / "hooks" / "hook-gi.repository.GtkSource.py"
    spec = importlib.util.spec_from_file_location("dayquay_gtksource_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class HookApi:
        def add_datas(self, values):
            self.datas = values

        def add_binaries(self, values):
            self.binaries = values

        def add_imports(self, *values):
            self.imports = values

    api = HookApi()
    module.hook(api)

    assert calls == [("GtkSource", "4", api)]
    assert api.datas == ["typelib", ("source/gtksourceview-4", "share/gtksourceview-4")]
    assert api.binaries == ["binary"]
    assert api.imports == ("hidden",)


def test_local_girepository_hook_collects_version_three_runtime(monkeypatch):
    calls = []

    class FakeModuleInfo:
        def __init__(self, name, version, hook_api=None):
            calls.append((name, version, hook_api))
            self.available = True

        def collect_typelib_data(self):
            return (["girepository-binary"], ["girepository-typelib"], ["dependency"])

    fake_gi = types.ModuleType("PyInstaller.utils.hooks.gi")
    fake_gi.GiModuleInfo = FakeModuleInfo
    monkeypatch.setitem(sys.modules, "PyInstaller", types.ModuleType("PyInstaller"))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils", types.ModuleType("PyInstaller.utils"))
    monkeypatch.setitem(
        sys.modules, "PyInstaller.utils.hooks", types.ModuleType("PyInstaller.utils.hooks")
    )
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks.gi", fake_gi)

    hook_path = (
        Path(__file__).parents[1]
        / "win"
        / "hooks"
        / "hook-gi.repository.GIRepository.py"
    )
    spec = importlib.util.spec_from_file_location("dayquay_girepository_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class HookApi:
        def add_datas(self, values):
            self.datas = values

        def add_binaries(self, values):
            self.binaries = values

        def add_imports(self, *values):
            self.imports = values

    api = HookApi()
    module.hook(api)

    assert calls == [("GIRepository", "3.0", api)]
    assert api.datas == ["girepository-typelib"]
    assert api.binaries == ["girepository-binary"]
    assert api.imports == ("dependency",)
