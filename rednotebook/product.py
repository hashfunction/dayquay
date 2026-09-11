"""DayQuay product boundaries that do not depend on GTK."""

import os
import shutil
import sys
import tempfile
from pathlib import Path


PRODUCT_NAME = "DayQuay"
LEGACY_PROFILE_NAME = ".rednotebook"
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
    """Point PyEnchant at the exact DLL shipped in a frozen DayQuay build."""
    if frozen is None:
        frozen = hasattr(sys, "frozen")
    if not frozen:
        return None
    environment = os.environ if environment is None else environment
    base_dir = Path(base_dir)
    candidates = (base_dir / "libenchant-2-2.dll", base_dir / "bin" / "libenchant-2-2.dll")
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            environment["PYENCHANT_LIBRARY_PATH"] = str(resolved)
            return resolved
    environment.pop("PYENCHANT_LIBRARY_PATH", None)
    raise ProductConfigurationError(
        f"Frozen DayQuay runtime is missing bundled libenchant-2-2.dll under {base_dir}"
    )


def legacy_profile_path(home_dir):
    return Path(home_dir) / LEGACY_PROFILE_NAME


def legacy_profile_available(legacy_dir):
    legacy_dir = Path(legacy_dir)
    return legacy_dir.is_dir() and any(
        (legacy_dir / relative).exists() for relative in _IMPORTABLE_PROFILE_PATHS
    )


def _profile_files(legacy_dir):
    if legacy_dir.is_symlink():
        raise LegacyImportError(f"Legacy profile is a symbolic link: {legacy_dir}")
    files = []
    for relative in _IMPORTABLE_PROFILE_PATHS:
        source = legacy_dir / relative
        if not source.exists():
            continue
        candidates = [source] if source.is_file() else sorted(source.rglob("*"))
        for candidate in candidates:
            if candidate.is_symlink():
                raise LegacyImportError(f"Legacy profile contains a symbolic link: {candidate}")
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
    config_file = destination / "configuration.cfg"
    if config_file.exists() and (not config_file.is_file() or config_file.stat().st_size):
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
        copied = []
        try:
            for _source, relative in files:
                source = staged / relative
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target, follow_symlinks=False)
                copied.append(target)
        except Exception:
            for target in reversed(copied):
                target.unlink(missing_ok=True)
            raise
    finally:
        shutil.rmtree(staged, ignore_errors=True)
    return tuple(sorted(relative.as_posix() for _source, relative in files))
