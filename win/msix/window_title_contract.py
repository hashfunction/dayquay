"""Exact fresh-journal title from production source; no GTK/profile imports.
SPDX-License-Identifier: GPL-2.0-or-later
Copyright 2026 Trieflow LLC.
Reviewed method below retains Jendrik Seipp 2008-2024 copyright; see ../../LICENSE.
"""

import argparse
import ast
import datetime
import json
import locale
from pathlib import Path
from types import SimpleNamespace

SOURCE_FILES = (
    "rednotebook/journal.py",
    "rednotebook/configuration.py",
    "rednotebook/util/dates.py",
    "rednotebook/external/elibintl.py",
    "win/msix/window_title_contract.py",
)
# Pin the reviewed stable title operation, not the transient MainWindow title.
# AST equality tolerates comments/formatting, but requires review if behavior drifts.
REVIEWED_METHOD = ast.parse(
    """
def set_frame_title(self):
    parts = [info.program_name]
    if self.title != "data":
        parts.append(self.title)
    parts.append(dates.format_date(self.config.read("exportDateFormat"), self.date))
    self.frame.main_frame.set_title(" - ".join(parts))
"""
).body[0]


def _tree(source, relative):
    return ast.parse((Path(source) / relative).read_text(encoding="utf-8"))


def _only(items, label):
    if len(items) != 1:
        raise ValueError("Ambiguous production title source: " + label)
    return items[0]


def source_title(source, day):
    info = _tree(source, "rednotebook/info.py")
    name = _only(
        [
            ast.literal_eval(n.value)
            for n in info.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "program_name" for t in n.targets)
        ],
        "name",
    )
    config = _only(
        [
            n
            for n in _tree(source, "rednotebook/configuration.py").body
            if isinstance(n, ast.ClassDef) and n.name == "Config"
        ],
        "Config",
    )
    defaults = _only(
        [
            ast.literal_eval(n.value)
            for n in config.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "defaults" for t in n.targets)
        ],
        "defaults",
    )
    journal = _only(
        [
            n
            for n in _tree(source, "rednotebook/journal.py").body
            if isinstance(n, ast.ClassDef) and n.name == "Journal"
        ],
        "Journal",
    )
    method = _only(
        [n for n in journal.body if isinstance(n, ast.FunctionDef) and n.name == "set_frame_title"],
        "set_frame_title",
    )
    if (
        name != "Jotmorrow"
        or defaults.get("exportDateFormat") != "%A, %x"
        or ast.dump(method) != ast.dump(REVIEWED_METHOD)
    ):
        raise ValueError("Stable journal title source requires renewed qualification review")
    formatter = _only(
        [
            n
            for n in _tree(source, "rednotebook/util/dates.py").body
            if isinstance(n, ast.FunctionDef) and n.name == "format_date"
        ],
        "format_date",
    )
    namespace = {"datetime": datetime}
    exec(
        compile(ast.Module(body=[formatter], type_ignores=[]), "production dates.py", "exec"),
        namespace,
    )
    namespace.update(
        info=SimpleNamespace(program_name=name),
        dates=SimpleNamespace(format_date=namespace["format_date"]),
    )
    exec(
        compile(
            ast.Module(body=[method], type_ignores=[]), "production Journal.set_frame_title", "exec"
        ),
        namespace,
    )
    titles = []
    instance = SimpleNamespace(
        title="data",
        date=day,
        config=SimpleNamespace(read=defaults.__getitem__),
        frame=SimpleNamespace(main_frame=SimpleNamespace(set_title=titles.append)),
    )
    namespace["set_frame_title"](instance)
    return _only(titles, "rendered title")


def create_title_contract(source, day=None):
    # Same locale initialization as elibintl._install(asglobal=True). The exact
    # recorded MSYS2 Python is used on Windows, matching the embedded runtime.
    locale.setlocale(locale.LC_ALL, "")
    day = datetime.date.today() if day is None else day
    title = source_title(source, day)
    if (
        not isinstance(title, str)
        or not title
        or len(title) > 512
        or any(c in title for c in "\r\n\0")
    ):
        raise ValueError("Unbounded production title")
    return dict(
        schemaVersion=1,
        localDate=day.isoformat(),
        locale=locale.setlocale(locale.LC_TIME),
        expectedTitle=title,
    )


def validate_title_contract(source, contract):
    # This is a same-run, fresh-profile qualification. A date/locale boundary
    # requires a new observation; it never broadens the title to a prefix match.
    expected = create_title_contract(source)
    if (
        not isinstance(contract, dict)
        or type(contract.get("schemaVersion")) is not int
        or contract != expected
    ):
        raise ValueError("Window title contract differs from current source/date/locale")
    return expected["expectedTitle"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = json.dumps(create_title_contract(args.source_root), ensure_ascii=False).encode("utf-8")
    with args.output.open("xb") as stream:
        stream.write(data)


if __name__ == "__main__":
    main()
