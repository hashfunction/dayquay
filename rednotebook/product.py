"""DayQuay product boundaries that do not depend on GTK."""

import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

from rednotebook import atomic


PRODUCT_NAME = "DayQuay"
LEGACY_PROFILE_NAME = ".rednotebook"
LEGACY_SETTINGS_IMPORT_NAME = "rednotebook-import.cfg"
_IMPORTABLE_PROFILE_PATHS = ("configuration.cfg", "data", "templates")
_PROFILE_PATH_KEYS = {"dataDir", "portable", "userDir"}


class ProductConfigurationError(RuntimeError):
    pass


class LegacyImportError(RuntimeError):
    pass


def default_user_dir(
    *, app_dir, home_dir, platform_name=None, environment=None, portable=False
):
    """Return the product-owned profile directory for the selected platform."""
    app_dir = Path(app_dir)
    home_dir = Path(home_dir)
    platform_name = platform_name or sys.platform
    environment = os.environ if environment is None else environment
    if portable:
        return app_dir / "user"
    if platform_name.startswith("win"):
        roaming = environment.get("APPDATA")
        if roaming:
            return Path(roaming) / PRODUCT_NAME
        return home_dir / "AppData" / "Roaming" / PRODUCT_NAME
    return home_dir / ".dayquay"


def configure_bundled_enchant(base_dir, *, frozen=None, environment=None):
    """Configure the relocatable Enchant prefix shipped in frozen DayQuay."""
    if frozen is None:
        frozen = hasattr(sys, "frozen")
    if not frozen:
        return None
    environment = os.environ if environment is None else environment
    # PyEnchant checks this override before PYENCHANT_LIBRARY_PATH. A frozen
    # application must use its own broker/provider prefix, even when inherited.
    environment.pop("PYENCHANT_ENCHANT_PREFIX", None)
    base_dir = Path(base_dir)
    candidate = base_dir / "bin" / "libenchant-2-2.dll"
    required = (
        candidate,
        base_dir / "lib" / "enchant-2" / "enchant_hunspell.dll",
        base_dir / "share" / "hunspell" / "en_US.aff",
        base_dir / "share" / "hunspell" / "en_US.dic",
    )
    missing = [path for path in required if not path.is_file()]
    if not missing:
        resolved = candidate.resolve()
        environment["PYENCHANT_LIBRARY_PATH"] = str(resolved)
        bundled_data = str((base_dir / "share").resolve())
        existing = [
            value
            for value in environment.get("XDG_DATA_DIRS", "").split(os.pathsep)
            if value
        ]
        bundled_key = os.path.normcase(os.path.abspath(bundled_data))
        existing = [
            value
            for value in existing
            if os.path.normcase(os.path.abspath(value)) != bundled_key
        ]
        environment["XDG_DATA_DIRS"] = os.pathsep.join([bundled_data, *existing])
        return resolved
    environment.pop("PYENCHANT_LIBRARY_PATH", None)
    raise ProductConfigurationError(
        "Frozen DayQuay runtime requires bin/libenchant-2-2.dll, its "
        f"lib/enchant-2 provider and share/hunspell en_US data under {base_dir}; "
        f"missing: {', '.join(str(path) for path in missing)}"
    )


def legacy_profile_path(home_dir):
    return Path(home_dir) / LEGACY_PROFILE_NAME


def legacy_profile_available(legacy_dir):
    legacy_dir = Path(legacy_dir)
    return legacy_dir.is_dir() and any(
        (legacy_dir / relative).exists() for relative in _IMPORTABLE_PROFILE_PATHS
    )


def legacy_settings_path(destination):
    return Path(destination) / LEGACY_SETTINGS_IMPORT_NAME


def _is_link_or_reparse(path):
    try:
        info = Path(path).lstat()
    except FileNotFoundError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & reparse_flag
    )


def _profile_files(legacy_dir):
    if _is_link_or_reparse(legacy_dir):
        raise LegacyImportError(f"Legacy profile is a symbolic link: {legacy_dir}")
    try:
        resolved_root = legacy_dir.resolve(strict=True)
    except OSError as exc:
        raise LegacyImportError(f"Legacy profile cannot be read: {legacy_dir}") from exc
    files = []
    for relative in _IMPORTABLE_PROFILE_PATHS:
        source = legacy_dir / relative
        if _is_link_or_reparse(source):
            raise LegacyImportError(f"Legacy profile contains a symbolic link: {source}")
        if not source.exists():
            continue
        candidates = [source] if source.is_file() else sorted(source.rglob("*"))
        for candidate in candidates:
            if _is_link_or_reparse(candidate):
                raise LegacyImportError(f"Legacy profile contains a symbolic link: {candidate}")
            try:
                candidate.resolve(strict=True).relative_to(resolved_root)
            except (OSError, ValueError) as exc:
                raise LegacyImportError(
                    f"Legacy profile entry escapes its profile: {candidate}"
                ) from exc
            if candidate.is_file():
                files.append((candidate, candidate.relative_to(legacy_dir)))
            elif not candidate.is_dir():
                raise LegacyImportError(
                    f"Legacy profile contains an unsupported entry: {candidate}"
                )
    return files


def _ensure_import_target_is_empty(destination):
    data_dir = destination / "data"
    if data_dir.exists() and (not data_dir.is_dir() or any(data_dir.iterdir())):
        raise LegacyImportError("DayQuay already contains journal data")
    templates_dir = destination / "templates"
    if templates_dir.exists() and (not templates_dir.is_dir() or any(templates_dir.iterdir())):
        raise LegacyImportError("DayQuay already contains templates")
    settings_file = legacy_settings_path(destination)
    if settings_file.exists():
        raise LegacyImportError("DayQuay already contains settings")


def _copy_import_file(source, target, relative):
    if relative.as_posix() != "configuration.cfg":
        shutil.copy2(source, target, follow_symlinks=False)
        return
    content = source.read_text(encoding="utf-8", errors="replace")
    safe_lines = []
    for line in content.splitlines(keepends=True):
        key = line.partition("=")[0].strip()
        if key not in _PROFILE_PATH_KEYS:
            safe_lines.append(line)
    target.write_text("".join(safe_lines), encoding="utf-8")


def _publish_import_directory(staged, destination, label):
    if not staged.exists():
        return False
    if destination.exists():
        if _is_link_or_reparse(destination) or not destination.is_dir():
            raise LegacyImportError(f"Import stopped at existing DayQuay {label}")
        try:
            destination.rmdir()
        except OSError as exc:
            raise LegacyImportError(f"Import stopped at existing DayQuay {label}") from exc
    try:
        atomic.rename_directory_no_replace(staged, destination)
    except (FileExistsError, NotImplementedError, OSError) as exc:
        raise LegacyImportError(f"Import stopped at existing DayQuay {label}") from exc
    return True


def _publish_import_settings(staged, destination):
    if not staged.exists():
        return False
    try:
        os.link(staged, destination)
    except FileExistsError as exc:
        raise LegacyImportError("Import stopped at existing DayQuay settings") from exc
    except OSError as exc:
        raise LegacyImportError("DayQuay could not publish imported settings safely") from exc
    return True


def import_legacy_profile(legacy_dir, destination):
    """Copy settings and journal files after a distinct, explicit user action."""
    legacy_dir = Path(legacy_dir)
    destination = Path(destination)
    if not legacy_profile_available(legacy_dir):
        raise LegacyImportError(f"No importable RedNotebook profile found at {legacy_dir}")
    files = _profile_files(legacy_dir)
    _ensure_import_target_is_empty(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=".dayquay-import-", dir=str(destination.parent)))
    try:
        for source, relative in files:
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_import_file(source, target, relative)

        destination.mkdir(exist_ok=True)
        published = []
        for directory_name, label in (("data", "data"), ("templates", "templates")):
            if _publish_import_directory(
                staged / directory_name, destination / directory_name, label
            ):
                published.extend(
                    relative.as_posix()
                    for _source, relative in files
                    if relative.parts[0] == directory_name
                )
        if _publish_import_settings(
            staged / "configuration.cfg", legacy_settings_path(destination)
        ):
            published.append(LEGACY_SETTINGS_IMPORT_NAME)
    finally:
        shutil.rmtree(staged, ignore_errors=True)
    return tuple(sorted(published))
