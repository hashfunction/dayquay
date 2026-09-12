# Jotmorrow

Jotmorrow 1.0.1 is a local desktop journal for dated entries, tags, attachments,
templates, search, exports, and verified portable backups. It is based on
RedNotebook 2.42 by Jendrik Seipp and contributors.

- [Product](https://jotmorrow.trieflow.com)
- [Support](https://jotmorrow.trieflow.com/support)
- [Privacy](https://jotmorrow.trieflow.com/privacy)
- [Application and dependency source](https://jotmorrow.trieflow.com/source)

The Windows application is `Jotmorrow.exe`; its MSIX version is `1.0.1.0`.
The renamed source is awaiting its exact Windows qualification. Previous
DayQuay runs remain historical evidence and do not qualify the renamed build.

## Existing journals and portable backups

The rename preserves `%APPDATA%\DayQuay` on Windows, `$HOME/.dayquay` on other
platforms, and `user` beside a portable application. Existing settings, journals,
templates, and previously written portable backups remain compatible. The
assigned Microsoft Store identity and application ID also remain unchanged.
No existing user profile is moved, renamed, or rewritten by the rename.

## Build and test

The qualified Windows stack is MSYS2 UCRT64, Python, GTK 3.24, GtkSourceView 4,
PyGObject, PyYAML, Enchant and Hunspell. See [Windows source build instructions](win/README.txt)
and [MSIX qualification and reviewed unsigned export](win/msix/README.md).
The workflow records exact native versions and archive hashes before building.

Run the application from a source checkout with the native dependencies
installed:

```sh
python3 rednotebook/journal.py
python3 -m pytest tests -q
python3 -m unittest discover -s win/msix -p 'test_*.py' -v
```

The Python distribution and desktop entry are named `jotmorrow`. Portable
Windows builds retain `Jotmorrow` as their application directory name and use the
same `user` subdirectory when portable mode is enabled.

## Attribution and source

Jotmorrow modifications and the original sunrise/journal mark are Copyright
2026 Trieflow contributors. RedNotebook is Copyright Jendrik Seipp and
contributors. Upstream artwork remains credited to Ciaran. The combined
application is GPL-3.0-or-later because it includes the GPL-3.0-or-later
spellcheck component. See [original license](LICENSE), [license texts](LICENSES),
[third-party notices](win/THIRD-PARTY-NOTICES.txt), and
[upstream file-level notices](debian/copyright).

The [upstream RedNotebook README](docs/UPSTREAM-REDNOTEBOOK-README.md) is retained
unchanged for attribution. Published dependency source archive names and old
run receipts retain their original DayQuay names; renaming those historical
assets would break their recorded provenance.
