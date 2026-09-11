"""Fail-closed discovery for source-to-package Windows inputs."""

from dataclasses import dataclass
from pathlib import Path


class MissingWindowsInput(RuntimeError):
    pass


@dataclass(frozen=True)
class EnchantInputs:
    binaries: tuple
    datas: tuple


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
    binaries = [(broker, ".")]
    binaries.extend((path, "lib/enchant-2") for path in providers)
    datas = [(path, "share/hunspell") for path in dictionaries]
    datas.append((dictionary_license, "LICENSES"))
    return EnchantInputs(tuple(binaries), tuple(datas))
