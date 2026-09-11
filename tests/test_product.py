import os
from pathlib import Path

import pytest

from rednotebook import product


def test_default_user_dir_is_independent_on_windows(tmp_path):
    appdata = tmp_path / "Roaming"

    assert product.default_user_dir(
        app_dir=tmp_path / "install",
        home_dir=tmp_path / "home",
        platform_name="win32",
        environment={"APPDATA": str(appdata)},
    ) == appdata / "DayQuay"


def test_default_user_dir_is_independent_on_unix(tmp_path):
    assert product.default_user_dir(
        app_dir=tmp_path / "install",
        home_dir=tmp_path / "home",
        platform_name="darwin",
        environment={},
    ) == tmp_path / "home" / ".dayquay"


def test_portable_user_dir_stays_beside_application(tmp_path):
    assert product.default_user_dir(
        app_dir=tmp_path / "install",
        home_dir=tmp_path / "home",
        platform_name="win32",
        environment={},
        portable=True,
    ) == tmp_path / "install" / "user"


def test_frozen_runtime_selects_actual_bundled_enchant_dll(tmp_path):
    dll = tmp_path / "libenchant-2-2.dll"
    dll.write_bytes(b"dll")
    environment = {"PYENCHANT_LIBRARY_PATH": "C:/unrelated/libenchant.dll"}

    selected = product.configure_bundled_enchant(
        tmp_path, frozen=True, environment=environment
    )

    assert selected == dll
    assert environment["PYENCHANT_LIBRARY_PATH"] == str(dll.resolve())


def test_non_frozen_runtime_does_not_override_enchant(tmp_path):
    environment = {"PYENCHANT_LIBRARY_PATH": "C:/development/enchant.dll"}

    assert product.configure_bundled_enchant(
        tmp_path, frozen=False, environment=environment
    ) is None
    assert environment["PYENCHANT_LIBRARY_PATH"] == "C:/development/enchant.dll"


def test_frozen_runtime_fails_when_bundled_enchant_is_missing(tmp_path):
    with pytest.raises(product.ProductConfigurationError, match="libenchant-2-2.dll"):
        product.configure_bundled_enchant(tmp_path, frozen=True, environment={})


def test_explicit_legacy_import_copies_data_without_modifying_source(tmp_path):
    legacy = tmp_path / ".rednotebook"
    destination = tmp_path / "DayQuay"
    (legacy / "data").mkdir(parents=True)
    (legacy / "templates").mkdir()
    (legacy / "data" / "2026-09.txt").write_text("1: {text: hello}\n", encoding="utf-8")
    (legacy / "templates" / "Weekly.txt").write_text("plan", encoding="utf-8")
    (legacy / "configuration.cfg").write_text(
        "showTagsPane=1\ndataDir=C:/old-profile/data\nuserDir=C:/old-profile\nportable=1\n",
        encoding="utf-8",
    )
    destination.mkdir()
    (destination / "configuration.cfg").write_text("", encoding="utf-8")
    (destination / "dayquay.log").write_text("current log", encoding="utf-8")

    imported = product.import_legacy_profile(legacy, destination)

    assert imported == ("configuration.cfg", "data/2026-09.txt", "templates/Weekly.txt")
    assert (destination / "data" / "2026-09.txt").read_text(encoding="utf-8") == (
        "1: {text: hello}\n"
    )
    assert (destination / "configuration.cfg").read_text(encoding="utf-8") == (
        "showTagsPane=1\n"
    )
    assert (destination / "dayquay.log").read_text(encoding="utf-8") == "current log"
    assert (legacy / "data" / "2026-09.txt").exists()


def test_legacy_import_requires_an_empty_dayquay_profile(tmp_path):
    legacy = tmp_path / ".rednotebook"
    destination = tmp_path / "DayQuay"
    (legacy / "data").mkdir(parents=True)
    (legacy / "data" / "2026-09.txt").write_text("month", encoding="utf-8")
    (destination / "data").mkdir(parents=True)
    (destination / "data" / "current.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(product.LegacyImportError, match="already contains journal data"):
        product.import_legacy_profile(legacy, destination)

    assert (destination / "data" / "current.txt").read_text(encoding="utf-8") == "keep"


def test_legacy_import_rejects_symlinked_content(tmp_path):
    legacy = tmp_path / ".rednotebook"
    destination = tmp_path / "DayQuay"
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (legacy / "data").mkdir(parents=True)
    os.symlink(outside, legacy / "data" / "linked.txt")

    with pytest.raises(product.LegacyImportError, match="symbolic link"):
        product.import_legacy_profile(legacy, destination)

    assert not destination.exists()
