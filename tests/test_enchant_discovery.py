"""Exercise the installed, source-pinned PyEnchant selector without native loading."""

import ast
import importlib.util
import os
from pathlib import Path

import pytest

from rednotebook import product


def _selected_enchant_library():
    spec = importlib.util.find_spec("enchant")
    assert spec is not None and spec.origin, "Install win/pyenchant-source-lock.txt first"
    source = Path(spec.origin).with_name("_enchant.py")
    nodes = []
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        nodes.append(node)
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "enchant_lib_path"
            for target in node.targets
        ):
            break
    else:
        pytest.fail("Installed PyEnchant source no longer exposes its reviewed selector")
    # Execute the actual installed imports, selector functions and selection
    # assignment. Stop before ctypes.LoadLibrary: fixture DLLs are inert bytes.
    namespace = {"__file__": str(source)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace["enchant_lib_path"]


@pytest.mark.parametrize("frozen", [False, True])
def test_real_pyenchant_prefix_precedence_respects_frozen_boundary(tmp_path, monkeypatch, frozen):
    bundle = tmp_path / "_internal"
    for relative in (
        "bin/libenchant-2-2.dll",
        "lib/enchant-2/enchant_hunspell.dll",
        "share/hunspell/en_US.aff",
        "share/hunspell/en_US.dic",
    ):
        path = bundle / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned fixture")
    foreign = tmp_path / "other-enchant"
    foreign_dll = foreign / "bin/libenchant-2.dll"
    foreign_dll.parent.mkdir(parents=True)
    foreign_dll.write_bytes(b"foreign fixture")
    monkeypatch.setenv("PYENCHANT_ENCHANT_PREFIX", str(foreign))
    monkeypatch.setenv("PYENCHANT_LIBRARY_PATH", str(foreign_dll))
    # The real selector mutates PATH in source mode; the product configures XDG
    # in frozen mode. Both must be restored after exercising these real paths.
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "other-share"))

    product.configure_bundled_enchant(bundle, frozen=frozen)

    expected = bundle / "bin/libenchant-2-2.dll" if frozen else foreign_dll
    assert Path(_selected_enchant_library()) == expected.resolve()
