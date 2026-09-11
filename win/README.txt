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
The runtime hook sets PYENCHANT_LIBRARY_PATH to the DLL inside the frozen app
before PyEnchant imports.

Optional legacy Inno installer handoff (MSIX remains root-owned):

  iscc /DREDNOTEBOOK_VERSION=2.42.0.1 win/rednotebook.iss

Do not distribute a binary until the Windows app itself has run successfully,
the package contents and uninstall behavior have been checked, and the complete
corresponding source URL is live. A successful native import probe alone is not
an application build.
