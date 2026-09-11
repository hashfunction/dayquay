# -----------------------------------------------------------------------
# Copyright (c) 2008-2024 Jendrik Seipp
#
# RedNotebook is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# RedNotebook is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with RedNotebook; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# -----------------------------------------------------------------------

import codecs
import calendar
import logging
import os
import re
import shutil
import stat
import sys

from rednotebook.data import Month


try:
    import yaml
except ImportError:
    logging.error("PyYAML not found. Please install it (python3-yaml).")
    sys.exit(1)

try:
    from yaml import CSafeLoader as _SafeLoader
    from yaml import CSafeDumper as Dumper

    logging.info("Using LibYAML")
except ImportError:
    from yaml import SafeDumper as Dumper
    from yaml import SafeLoader as _SafeLoader

    logging.info("Using PyYAML")


class Loader(_SafeLoader):
    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in seen
                seen.add(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable mapping key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
        return super().construct_mapping(node, deep=deep)


MAX_MONTH_BYTES = 16 * 1024 * 1024
MAX_YAML_EVENTS = 200_000
MAX_YAML_DEPTH = 32
MAX_CATEGORY_DEPTH = 16
MAX_SCHEMA_NODES = 100_000
MAX_SCALAR_CHARS = 8 * 1024 * 1024


class InvalidJournalData(ValueError):
    pass


def format_year_and_month(year, month):
    return f"{year:04d}-{month:02d}"


def get_journal_files(data_dir):
    # Format: 2010-05.txt
    date_exp = re.compile(r"(\d{4})-(\d{2})\.txt$")

    for file in sorted(os.listdir(data_dir)):
        if match := date_exp.match(file):
            year = int(match[1])
            month = int(match[2])
            if month not in range(1, 12 + 1):
                raise InvalidJournalData(f"Invalid month number in journal file: {file}")
            path = os.path.join(data_dir, file)
            yield (path, year, month)
        else:
            logging.debug(f"{file} is not a valid month filename")


def _validate_yaml_events(contents):
    depth = 0
    event_count = 0
    try:
        for event in yaml.parse(contents, Loader=Loader):
            event_count += 1
            if event_count > MAX_YAML_EVENTS:
                raise InvalidJournalData("Journal YAML exceeds the event limit")
            if isinstance(event, yaml.events.AliasEvent):
                raise InvalidJournalData("Journal YAML aliases are not allowed")
            if isinstance(event, (yaml.events.MappingStartEvent, yaml.events.SequenceStartEvent)):
                depth += 1
                if depth > MAX_YAML_DEPTH:
                    raise InvalidJournalData("Journal YAML nesting exceeds the limit")
            elif isinstance(event, (yaml.events.MappingEndEvent, yaml.events.SequenceEndEvent)):
                depth -= 1
    except yaml.YAMLError as exc:
        raise InvalidJournalData(f"Invalid journal YAML: {exc}") from exc


def _validate_category(value, depth, state):
    if depth > MAX_CATEGORY_DEPTH:
        raise InvalidJournalData("Journal category nesting exceeds the limit")
    if value is None:
        return
    if not isinstance(value, dict):
        raise InvalidJournalData("Journal category values must be mappings or null")
    for key, child in value.items():
        state[0] += 1
        if state[0] > MAX_SCHEMA_NODES:
            raise InvalidJournalData("Journal structure exceeds the node limit")
        if not isinstance(key, str) or not key or len(key) > MAX_SCALAR_CHARS:
            raise InvalidJournalData("Journal category names must be bounded strings")
        _validate_category(child, depth + 1, state)


def _validate_month_schema(contents, year_number, month_number):
    if contents is None:
        return {}
    if not isinstance(contents, dict):
        raise InvalidJournalData("Journal month must be a mapping")
    state = [0]
    maximum_day = calendar.monthrange(year_number, month_number)[1]
    for day_number, day_content in contents.items():
        state[0] += 1
        if type(day_number) is not int or day_number not in range(1, maximum_day + 1):
            raise InvalidJournalData(f"Invalid journal day number: {day_number!r}")
        if not isinstance(day_content, dict):
            raise InvalidJournalData(f"Journal day {day_number} must be a mapping")
        if "text" not in day_content or not isinstance(day_content["text"], str):
            raise InvalidJournalData(f"Journal day {day_number} requires string text")
        if len(day_content["text"]) > MAX_SCALAR_CHARS:
            raise InvalidJournalData(f"Journal day {day_number} text exceeds the limit")
        for category, value in day_content.items():
            state[0] += 1
            if state[0] > MAX_SCHEMA_NODES:
                raise InvalidJournalData("Journal structure exceeds the node limit")
            if not isinstance(category, str) or not category or len(category) > MAX_SCALAR_CHARS:
                raise InvalidJournalData("Journal day keys must be bounded strings")
            if category != "text":
                _validate_category(value, 1, state)
    return contents


def load_month_from_disk(
    path, year_number, month_number, *, max_bytes=MAX_MONTH_BYTES
):
    path = os.fspath(path)
    try:
        file_size = os.path.getsize(path)
        if file_size > max_bytes:
            raise InvalidJournalData(
                f"Journal month exceeds byte limit ({file_size} > {max_bytes}): {path}"
            )
        with codecs.open(path, "rb", encoding="utf-8") as month_file:
            logging.debug(f'Loading file "{path}"')
            contents = month_file.read(max_bytes + 1)
        if len(contents.encode("utf-8")) > max_bytes:
            raise InvalidJournalData(f"Journal month exceeds byte limit: {path}")
        _validate_yaml_events(contents)
        try:
            month_contents = yaml.load(contents, Loader=Loader)
        except yaml.YAMLError as exc:
            raise InvalidJournalData(f"Invalid journal YAML in {path}: {exc}") from exc
        month_contents = _validate_month_schema(month_contents, year_number, month_number)
        return Month(
            year_number,
            month_number,
            month_contents,
            os.path.getmtime(path),
        )
    except UnicodeError as exc:
        raise InvalidJournalData(f"Journal month is not valid UTF-8: {path}") from exc
    except OSError as exc:
        raise InvalidJournalData(f"Journal month could not be read: {path}") from exc


def _load_month_from_disk(path, year_number, month_number):
    """
    Load the month file at path and return a month object

    If an error occurs, return None
    """
    try:
        return load_month_from_disk(path, year_number, month_number)
    except InvalidJournalData as exc:
        logging.error(str(exc))
    # If we continued here, the possibly corrupted file would be overwritten.
    sys.exit(1)


def load_all_months_from_disk(data_dir, *, raise_on_error=False):
    """
    Load all months and return a directory mapping year-month values
    to month objects.
    """
    months = {}

    logging.debug(f'Starting to load files in dir "{data_dir}"')
    for path, year_number, month_number in get_journal_files(data_dir):
        load = load_month_from_disk if raise_on_error else _load_month_from_disk
        if month := load(path, year_number, month_number):
            months[format_year_and_month(year_number, month_number)] = month

    logging.debug(f'Finished loading files in dir "{data_dir}"')
    return months


def _get_dict(month):
    return {day_number: day.content for day_number, day in month.days.items() if not day.empty}


def _save_month_to_disk(month, journal_dir):
    """
    Return whether data was written to disk.

    When overwriting 2014-12.txt:
        write new content to 2014-12.new.txt
        check that new file is valid month file
        cp 2014-12.txt 2014-12.old.txt
        mv 2014-12.new.txt 2014-12.txt
        rm 2014-12.old.txt
    """
    content = _get_dict(month)

    def get_filename(infix):
        year_and_month = format_year_and_month(month.year_number, month.month_number)
        return os.path.join(journal_dir, f"{year_and_month}{infix}.txt")

    old = get_filename(".old")
    new = get_filename(".new")
    filename = get_filename("")

    # Do not save empty month files.
    if not content and not os.path.exists(filename):
        return False

    with codecs.open(new, "wb", encoding="utf-8") as f:
        # Write readable unicode and no Python directives.
        yaml.dump(content, f, Dumper=Dumper, allow_unicode=True)

    # Check that month file was written to disk successfully.
    written_month = _load_month_from_disk(new, month.year_number, month.month_number)
    if _get_dict(written_month) != content:
        try:
            os.remove(new)
        except OSError:
            pass
        raise OSError("writing month file to disk failed")

    if os.path.exists(filename):
        mtime = os.path.getmtime(filename)
        if mtime != month.mtime:
            conflict = get_filename(f".CONFLICT_BACKUP{mtime}")
            logging.debug(
                f"Last edit time of {filename} conflicts with edit time at file load\n"
                f"--> Backing up to {conflict}"
            )
            shutil.copy2(filename, conflict)
        shutil.copy2(filename, old)
    # Prevent save failures on network and cloud drives.
    if os.path.exists(filename):
        os.remove(filename)
    shutil.move(new, filename)
    if os.path.exists(old):
        os.remove(old)

    try:
        # Make file readable and writable only by the owner.
        os.chmod(filename, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

    month.edited = False
    month.mtime = os.path.getmtime(filename)
    logging.info(f"Wrote file {filename}")
    return True


def save_months_to_disk(months, journal_dir, exit_imminent=False, saveas=False):
    """
    Update the journal on disk and return if something had to be written.
    """
    something_saved = False
    for month in months.values():
        # We always need to save everything when we are "saving as".
        if month.edited or saveas:
            something_saved |= _save_month_to_disk(month, journal_dir)

    return something_saved
