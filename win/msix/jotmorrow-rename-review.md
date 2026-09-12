# Jotmorrow 1.0.1 source rename review

Prepared 2026-09-12 from independently reviewed source
`da80c3ceca1e416daf0bdec91ff6a619eddb6bc4`.
The approved reserved name is **Jotmorrow**, with canonical product URL
`https://jotmorrow.trieflow.com`.

## Current candidate

The application, native executable and portable build directory are Jotmorrow.
The application version is `1.0.1`; both fixed MSIX modes use `1.0.1.0`.
The reviewed unsigned Store output is `Jotmorrow_1.0.1.0_x64.msix`, and the
disposable package is `Jotmorrow.Qualification_1.0.1.0_x64.msix`.
The workflow artifact names are `Jotmorrow-native-qualification` and
`Jotmorrow-unsigned-store-package`.

The title, About dialog, tray, help, menus, new backup/export filenames, Python
distribution/entry point, desktop metadata, native build/installer metadata,
current documentation and project-owned notices use the approved name and
canonical links. The original journal/sunrise icon is retained: its SVG title
and filenames change, while its geometry and all nine PNGs plus the Windows ICO
retain their original bytes. No fabricated or relabelled Windows screenshot is
included.

## Compatibility and unchanged boundaries

- Assigned Store identity: `1659hashfunction.DayQuay`.
- Publisher: `CN=B6A2631A-FD32-45CC-AE12-82466975F528`; publisher display name:
  `hashfunction`; ApplicationId: `DayQuay`.
- GTK application ID: `com.trieflow.DayQuay`; Inno Setup application GUID is
  unchanged.
- Existing `%APPDATA%\DayQuay`, Windows fallback `AppData\Roaming\DayQuay`,
  Unix `.dayquay`, and portable `user` profile paths are unchanged. Display
  branding is separated from `PROFILE_DIRECTORY_NAME`.
- Backup format `dayquay-backup`, version 1, and `dayquay-manifest.json` remain
  readable and writable. Automatic backup collection excludes both historical
  `DayQuay-Backup` and current `Jotmorrow-Backup` names, preserving the previous
  exclusion for existing journals.
- Upstream RedNotebook authors, source URLs, original license texts, dependency
  notices, and the established public repository remain unchanged. Internal
  helper names, environment variables, temporary ownership markers and schema
  identifiers retain their historical names where they are not display branding.

The qualification title/executable expectations now require Jotmorrow exactly.
Both fixed identity modes still require normal broker activation, retained
process/window/foreground ownership, the real journal/tag/save/reopen/backup/
restore workflow, independent file/YAML/ZIP assertions, protected original
bytes, normal process stop, uninstall and marker-owned cleanup. No timeout,
input, acceptance or cleanup gate is relaxed.

## Source-publication binding

Every pre-existing field of `native-source-publication.json` is unchanged from
the reviewed base. Its historical product, source/run commits, source page,
published asset filenames, archive/manifest hashes, native input maps and audit
results remain historical evidence. The original public dependency source
collection is still the `native-sources-2026-09-11-df058` release in
`hashfunction/dayquay`; this rename does not publish replacement native assets.

A separate `current_application` section identifies Jotmorrow 1.0.1 and its new
canonical source page, and binds the 38 current application inputs from the
actual packaging source inventory. The 649 unchanged notice supplement/index
inputs make the complete inventory 687 entries. All 178 native archive inputs,
89 native versions, 1,165 mapped vendor payload entries and 766 original notice
payload entries remain bound by the existing native closure checks.

The export validator now rejects a changed current application source hash or
version, alongside all existing native/source/notice mutations. The separate
clean-checkout and exact reviewed public Git tree checks continue to bind the
entire source, including packaging/workflow helpers beyond those 38 explicit
inputs. Only a new exact-source, same-run/attempt Windows qualification can
authorize the unsigned Jotmorrow export.

The former root upstream README is preserved byte-for-byte in
`docs/UPSTREAM-REDNOTEBOOK-README.md`; the former MSIX qualification README is
preserved byte-for-byte in `win/msix/HISTORICAL-QUALIFICATION.md`. Existing review
reports and retained native run evidence are unchanged.

## Local checks

The following checks passed on this Mac:

- Full MSIX Python suite: 89 tests passed before the final source-map regression
  was added. Subsequent focused reruns cover all changed tests: installed
  workflow (23), fixed Store identity (2), source publication (3), and the full
  unsigned export boundary (8).
- All nine existing PowerShell fixture suites passed. The fixed identity suite
  was rerun after adding independent executable/version/ApplicationId assertions
  and passed both identities, 20 changed metadata cases, two cross-mode records
  and arbitrary-mode refusal.
- 85 focused application tests passed, covering product/version/profile
  compatibility, an independently serialized pre-rename backup, actual backup
  exclusion/readback, backup/restore failure boundaries, source build layout,
  the real PyInstaller dependency algorithm, the real pinned PyEnchant selector,
  journal days and hashtags.
- Independent readback confirmed every historical source-publication field was
  unchanged, all 38 current source records matched actual files, the 649 notice
  supplement/index entries were unchanged, all ten raster icon assets were
  byte-identical under their new names, and both moved historical documents
  were byte-identical.
- `git diff --check` passed.
- The real source-map regression failed after the final icon-export filename
  correction until its current source record was refreshed, then passed.
  `bash -n` also passed for the renamed icon export script.

Commands (run from the source root):

```sh
python3 -m unittest discover -s win/msix -p 'test_*.py' -v
python3 -m unittest discover -s win/msix -p 'test_installed_workflow.py' -v
python3 -m unittest discover -s win/msix -p 'test_store_identity.py' -v
python3 -m unittest discover -s win/msix -p 'test_source_publication.py' -v
python3 -m unittest discover -s win/msix -p 'test_export_store_package.py' -v
PYTHONPATH=/private/tmp/dayquay-pyinstaller-review-kixc2lbk/core:/private/tmp/pyenchant-source.RUMDZB \
  python3 -m pytest tests/test_rebranding.py tests/test_backup.py \
  tests/test_restore.py tests/test_restore_flow.py tests/test_product.py \
  tests/test_info.py tests/test_windows_packaging.py tests/test_enchant_layout.py \
  tests/test_enchant_discovery.py tests/test_day.py tests/test_hashtags.py -q
```

The two retained dependency source roots contain qualified PyInstaller 6.22.1
and PyEnchant 3.3.0. They supply the actual Python algorithms used by the tests;
the tests do not load native Windows DLLs on this Mac. The first local run had
three missing-package failures; supplying those retained sources resolved them
without changing or skipping tests.

The full application suite cannot collect on the local Python installation
because `gi` is absent (four affected modules: configuration, filesystem,
markup and utils). The Windows workflow still runs the complete native-backed
application suite with real GTK dependencies. Local tests do not claim native
Windows loading, installed UI success, marketing screenshots, unsigned export,
Store submission or certification.

## Required next evidence

Independent review and a new public source snapshot precede the actual renamed
Windows run. That run must rebuild Jotmorrow, qualify both fixed identities with
the complete current consumer workflow, and retain genuinely observed renamed
screenshots. The optional reviewed unsigned export must pass its exact-source
and source-publication gates. Historical successful DayQuay run `34676387900`
remains evidence for its original source only. Website, parent release status,
Store listing and public source deployment are outside this source candidate.
