DAYQUAY WINDOWS SOURCE BUILD
============================

The qualified build environment is MSYS2 UCRT64. The root-owned workflow
.github/workflows/build-windows.yml installs the native packages, records the
exact installed versions, downloads those same archives, compares the two
inventories, and hashes every archive before tests or packaging.

From an MSYS2 UCRT64 shell at the repository root, after installing the package
set listed in that workflow:

  bash win/record-msys2-inputs.sh
  python -m pip install --no-deps --no-build-isolation --no-binary=:all: \
    --require-hashes -r win/pyenchant-source-lock.txt
  export PYENCHANT_LIBRARY_PATH="$(cygpath -m "$MINGW_PREFIX/bin/libenchant-2-2.dll")"
  python win/dayquay-runtime-probe.py
  python -m pytest tests -q
  python -m PyInstaller --clean --noconfirm --workpath=C:/build \
    --distpath=C:/ win/rednotebook.spec

The spec derives the repository from SPECPATH, requires MINGW_PREFIX, selects
GtkSourceView 4 through hook configuration, includes the local resource hook,
and stages Enchant's ABI DLL, Hunspell provider, en_US dictionary and license.
The runtime hook points PYENCHANT_LIBRARY_PATH at
``_internal/bin/libenchant-2-2.dll`` before PyEnchant imports. Keeping the DLL
under ``bin`` is required because PyEnchant 3.3 derives Enchant's relocatable
prefix from the DLL's parent directory. The hook also prepends
``_internal/share`` to XDG_DATA_DIRS so the Hunspell provider can find the
packaged en_US dictionary without redirecting the user's Enchant config folder.
Frozen setup removes an inherited ``PYENCHANT_ENCHANT_PREFIX`` because PyEnchant
checks that override before ``PYENCHANT_LIBRARY_PATH``. Source-mode launches keep
both user overrides unchanged. ``tests/test_enchant_discovery.py`` executes the
installed, source-pinned PyEnchant selector up to (but not including) native DLL
loading, checking both modes against a real foreign-prefix fixture.

PyInstaller 6.22.1 independently collects the Hunspell provider's linked broker
at the bundle root during PE dependency analysis, even when the broker is an
explicit ``bin`` input. After Analysis, the spec retains the explicit bin entry
and removes only root/bin duplicates whose resolved source is that same qualified
broker. Foreign sources, wrong TOC types/destinations or a lost bin entry fail
the build. Other binaries, including Hunspell/GLib dependencies, are unchanged;
the package inventory still refuses a flat broker and requires the provider and
dictionary. ``tests/test_enchant_layout.py`` executes the installed PyInstaller
dependency-TOC algorithm and real spec wiring with only native PE import discovery
adapted to the retained provider import graph. Windows loading remains required.

Optional legacy Inno installer handoff (MSIX remains root-owned):

  iscc /DREDNOTEBOOK_VERSION=2.42.0.1 win/rednotebook.iss

Do not distribute a binary until the Windows app itself has run successfully,
the package contents and uninstall behavior have been checked, and the complete
corresponding source URL is live. A successful native import probe alone is not
an application build.
