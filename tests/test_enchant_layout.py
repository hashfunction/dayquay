"""Real PyInstaller dependency-TOC algorithm and Jotmorrow spec integration.

Only native PE import discovery is adapted to the retained Enchant/Hunspell
import graph. DLL fixture bytes are inert; native loading remains a Windows gate.
"""

import ast
import importlib.util
import logging
import os
from pathlib import Path
import pathlib
import runpy
import sys
import types

import pytest

from win import build_support


@pytest.fixture
def enchant_prefix(tmp_path):
    prefix = tmp_path / "ucrt64"
    for relative in (
        "bin/libenchant-2-2.dll",
        "bin/libglib-2.0-0.dll",
        "bin/libhunspell-1.7-0.dll",
        "lib/enchant-2/enchant_hunspell.dll",
        "share/hunspell/en_US.aff",
        "share/hunspell/en_US.dic",
        "share/licenses/hunspell-en/Copyright_en_US",
    ):
        path = prefix / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
    return prefix


def _actual_dependency_analysis(prefix, binaries):
    spec = importlib.util.find_spec("PyInstaller")
    assert spec is not None and spec.origin, "Install the qualified PyInstaller first"
    source = Path(spec.origin).parent / "depend/bindepend.py"
    names = {
        "_get_paths_for_parent_directory_preservation",
        "_select_destination_directory",
        "binary_dependency_analysis",
    }
    nodes = [
        node
        for node in ast.parse(source.read_text(encoding="utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert len(nodes) == len(names), "PyInstaller dependency-analysis interface changed"
    broker = prefix / "bin/libenchant-2-2.dll"
    provider = prefix / "lib/enchant-2/enchant_hunspell.dll"
    glib = prefix / "bin/libglib-2.0-0.dll"
    hunspell = prefix / "bin/libhunspell-1.7-0.dll"
    imports = {broker: {glib}, provider: {broker, glib, hunspell}}
    namespace = {
        "pathlib": pathlib,
        "os": os,
        "sys": sys,
        "logger": logging.getLogger(__name__),
        "compat": types.SimpleNamespace(is_win=True, is_darwin=False),
        "dylib": types.SimpleNamespace(include_library=lambda _path: True),
        "get_imports": lambda source, _search: {
            (path.name, str(path)) for path in imports.get(Path(source), set())
        },
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace["binary_dependency_analysis"](binaries, symlink_suppression_patterns=[])


def test_actual_spec_removes_only_verified_flat_duplicate_after_dependency_analysis(
    enchant_prefix, monkeypatch
):
    collected = {}
    monkeypatch.setenv("MINGW_PREFIX", str(enchant_prefix))
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))

    def analysis(_scripts, **kwargs):
        binaries = [
            (str(Path(destination) / Path(source).name), source, "BINARY")
            for source, destination in kwargs["binaries"]
        ]
        expanded = _actual_dependency_analysis(enchant_prefix, binaries)
        assert "libenchant-2-2.dll" in [row[0] for row in expanded]
        collected["before"] = list(expanded)
        return types.SimpleNamespace(binaries=expanded, datas=kwargs["datas"], pure=[], scripts=[])

    def collect(_exe, binaries, _datas, **_kwargs):
        collected["after"] = binaries

    runpy.run_path(
        str(Path(__file__).parents[1] / "win/rednotebook.spec"),
        init_globals={
            "SPECPATH": str(Path(__file__).parents[1] / "win"),
            "Analysis": analysis,
            "PYZ": lambda _pure: None,
            "EXE": lambda *_args, **_kwargs: None,
            "COLLECT": collect,
        },
    )
    names = [Path(row[0]).as_posix() for row in collected["after"]]
    assert names.count("bin/libenchant-2-2.dll") == 1
    assert "libenchant-2-2.dll" not in names
    assert {row for row in collected["after"] if "libenchant-2-2.dll" not in row[0]} == {
        row for row in collected["before"] if "libenchant-2-2.dll" not in row[0]
    }


@pytest.mark.parametrize(
    "mutation", ["foreign", "missing", "missing-bin", "data", "symlink", "wrong-directory"]
)
def test_layout_refuses_to_hide_unqualified_broker_rows(enchant_prefix, tmp_path, mutation):
    broker = enchant_prefix / "bin/libenchant-2-2.dll"
    rows = [("bin/libenchant-2-2.dll", str(broker), "BINARY")]
    if mutation == "foreign":
        foreign = tmp_path / "foreign.dll"
        foreign.write_bytes(
            broker.read_bytes()
        )  # Same bytes do not establish qualified source identity.
        rows.append(("libenchant-2-2.dll", str(foreign), "BINARY"))
    elif mutation == "missing":
        rows.clear()
    elif mutation == "missing-bin":
        rows = [("libenchant-2-2.dll", str(broker), "BINARY")]
    elif mutation in ("data", "symlink"):
        rows.append(("libenchant-2-2.dll", str(broker), mutation.upper()))
    else:
        rows.append(("other/libenchant-2-2.dll", str(broker), "BINARY"))
    original = list(rows)
    with pytest.raises(build_support.MissingWindowsInput):
        build_support.normalize_enchant_binaries(rows, broker)
    assert rows == original
