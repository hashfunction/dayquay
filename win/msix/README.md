# Jotmorrow Windows qualification and reviewed unsigned export

Current application version: **1.0.1**. MSIX version: **1.0.1.0**.
The production directory is `dist/Jotmorrow`, containing `Jotmorrow.exe`.
The exact renamed Windows build and consumer workflow remain pending.

## Fixed identities

| Mode | Identity name | Publisher | Application ID | Executable |
| --- | --- | --- | --- | --- |
| Disposable qualification | `Trieflow.Jotmorrow.Qualification` | `CN=Jotmorrow-CI-Qualification` | `DayQuay` | `Jotmorrow.exe` |
| Assigned Store identity | `1659hashfunction.DayQuay` | `CN=B6A2631A-FD32-45CC-AE12-82466975F528` | `DayQuay` | `Jotmorrow.exe` |

Both use x64, version `1.0.1.0`, and the existing `runFullTrust` capability.
Store publisher display name remains `hashfunction`. The Store identity,
application ID, GTK application ID and existing data locations are retained for
update compatibility. Customer-facing display names are Jotmorrow.

## Actual installed workflow

`qualify-msix.ps1` builds and qualifies both fixed identity modes sequentially.
It retains all source, native input, notice, package, SDK unpack, executable,
module, broker process and window checks. Each installed consumer receives an
exclusively created fresh fixture in the established `%APPDATA%\DayQuay` profile
location; an existing profile or matching registration causes refusal.

The normal installed UI creates a journal entry and tags, saves it, opens a
different journal and returns, appends and saves a marker, creates a ZIP backup,
restores into a fresh destination, and preserves the original journal and ZIP.
Independent file, YAML and ZIP assertions must pass. The retained process must
then stop normally; uninstall and owned profile/certificate cleanup must pass.
No test fixture, screenshot or historical receipt substitutes for those gates.

The title contract executes the reviewed production title method and actual date
formatter. It requires `Jotmorrow - <localized date>` and the corresponding exact
named-journal titles, within the unchanged timeouts and ownership checks.
Metadata and unedited diagnostic screenshots are retained under
`Jotmorrow-native-qualification`.

## Explicit reviewed unsigned export

After independent source review, `workflow_dispatch` can request
`export_store_package=true` and `reviewed_public_source=<exact public commit>`.
The export gate requires that exact public commit/tree, clean checkout,
same-run/attempt receipts, complete installed workflow, normal cleanup, and the
reviewed native source closure. It independently reconstructs current inputs
and verifies the strict unsigned MSIX before and after copying.

Only `Jotmorrow_1.0.1.0_x64.msix` and the last-written `release-ready.json` are
retained under `Jotmorrow-unsigned-store-package`. A late failure removes only
unchanged output owned by that export; changed or foreign files are preserved.
Temporary signed installation copies and private certificate material are
excluded. The receipt does not claim Store submission or certification.

The canonical source page is <https://jotmorrow.trieflow.com/source>. The already
published native dependency archive and source manifest keep their original
DayQuay filenames, release tag and hashes. `native-source-publication.json`
separately records the historical native audit and current application source
inputs, so a renamed application cannot reuse a stale source map. Changed
native dependencies require renewed source review.

## Checks and retained history

```sh
python3 -m unittest discover -s win/msix -p 'test_*.py' -v
```

Run all PowerShell fixture scripts listed in `.github/workflows/build-windows.yml`
before the native package/install steps. These fixtures exercise ownership and
failure boundaries and do not claim native application success.

[Historical qualification notes](HISTORICAL-QUALIFICATION.md) and the existing
review reports are retained without rewriting their source commits, product
names, version numbers or observed Windows outcomes. See
[Jotmorrow rename review](jotmorrow-rename-review.md) for current scope and checks.
