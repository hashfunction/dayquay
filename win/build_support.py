"""Fail-closed discovery for source-to-package Windows inputs."""

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath


class MissingWindowsInput(RuntimeError):
    pass


@dataclass(frozen=True)
class EnchantInputs:
    binaries: tuple
    datas: tuple


def normalize_enchant_binaries(binaries, broker):
    """Keep the qualified bin broker after PyInstaller expands PE dependencies."""
    try:
        expected = Path(broker).resolve(strict=True)
        if not expected.is_file():
            raise OSError("Broker source is not a file")
    except OSError as exc:
        raise MissingWindowsInput(f"Missing qualified Enchant broker source: {broker}") from exc
    name = "libenchant-2-2.dll"
    normalized = []
    found_bin = False
    for row in binaries:
        destination, source, kind = row
        path = PureWindowsPath(destination)
        if path.name.casefold() != name:
            normalized.append(row)
            continue
        target = path.as_posix().casefold()
        if target not in (name, f"bin/{name}") or kind != "BINARY":
            raise MissingWindowsInput(f"Unexpected Enchant broker TOC entry: {row}")
        try:
            same_source = Path(source).resolve(strict=True) == expected
        except OSError as exc:
            raise MissingWindowsInput(f"Missing Enchant broker TOC source: {source}") from exc
        if not same_source:
            raise MissingWindowsInput(f"Unqualified Enchant broker TOC source: {source}")
        if target == f"bin/{name}" and not found_bin:
            normalized.append((f"bin/{name}", str(expected), "BINARY"))
            found_bin = True
    if not found_bin:
        raise MissingWindowsInput("Dependency analysis lost the explicit bin Enchant broker")
    return normalized


def resolve_enchant_inputs(prefix):
    prefix = Path(prefix)
    broker = prefix / "bin" / "libenchant-2-2.dll"
    providers = [prefix / "lib" / "enchant-2" / "enchant_hunspell.dll"]
    dictionaries = sorted((prefix / "share" / "hunspell").glob("en_US.*"))
    dictionary_license = prefix / "share" / "licenses" / "hunspell-en" / "Copyright_en_US"
    if not broker.is_file():
        raise MissingWindowsInput(f"Missing Enchant ABI broker: {broker}")
    if not providers[0].is_file():
        raise MissingWindowsInput(f"Missing Enchant provider: {providers[0]}")
    suffixes = {path.suffix.lower() for path in dictionaries}
    if not {".aff", ".dic"}.issubset(suffixes):
        raise MissingWindowsInput(
            f"Missing en_US Hunspell dictionary under {prefix / 'share' / 'hunspell'}"
        )
    if not dictionary_license.is_file():
        raise MissingWindowsInput(f"Missing en_US dictionary license: {dictionary_license}")
    # PyEnchant derives Enchant's relocatable prefix as the parent of the DLL's
    # bin directory. Keeping the broker in bin is required for provider lookup.
    binaries = [(broker, "bin")]
    binaries.extend((path, "lib/enchant-2") for path in providers)
    datas = [(path, "share/hunspell") for path in dictionaries]
    datas.append((dictionary_license, "LICENSES"))
    return EnchantInputs(tuple(binaries), tuple(datas))
