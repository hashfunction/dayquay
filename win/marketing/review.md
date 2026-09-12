# Jotmorrow capture-only candidate review

Base local commit: `efc32e55aca4aee02056ddbf2101fcfb7e54ca5b`. The qualified Store binary/public source/run remain pinned in `capture_checks.py` and the workflow. Only new `win/marketing` helpers/fixtures/docs and `.github/workflows/marketing-screenshots.yml` are added. No runtime, package build, installed qualification, product artwork, source release or customer data compatibility is changed.

## Evidence and implementation

Read-only verification against the actual retained successful artifacts passed: original unsigned MSIX 39,743,804 bytes / SHA-256 `47b1b5153eedbbf4709ff8dd143164ff90445009137682722da4951e13b066fe`; all 1,976 payload entries, source/run binding, original successful journal/backup/restore/zero-close/uninstall/profile-cleanup receipts and each readiness evidence hash verified. Artifact IDs and sizes were retrieved from the actual GitHub run metadata before writing the download helper.

The new capture driver imports the exact qualified checkout's existing `_WindowsInput` and independent save/backup/restore byte oracles. It changes the sample text to an original fictional current-day journal; actual source hashtag recognition is regression-tested. The only extra keyboard action is bounded Ctrl+Home to place the saved entry's beginning in view, using the same final SendInput ownership and foreground checks. The new subclass records the actual restore confirmation before the original restore method confirms it.

Capture windows are moved/resized natively, with a real enumerated 1920x1080 display and 1440x900 main window. The full native main-window pixels are copied from the screen after exact retained process/package/module, HWND, title, DPI, foreground and unclipped bounds checks. The same snapshot is required after capture. A small legitimate restore confirmation is checked for full containment inside the main frame; it is not subjected to the qualification helper's unrelated minimum main-window size. Capture PNG hashes are rechecked before normal close.

The capture-specific lifecycle retains the original unsigned source, uses an ephemeral nonexportable signing key, proves exact successful-Add registration ownership, verifies the complete installed payload and fresh runtime modules before/after the UI path, and retains the actual process handle. Failed Add never grants removal ownership; an unproven active process prevents profile cleanup. Existing profile-marker cleanup and verified platform-module functions are reused. Display test/apply/restore follows the existing Cut native capture helper, with the requested exact 1920x1080 mode. No site or Store status is touched.

## Local validation

- `python3 -m unittest discover -s win/marketing -p 'test_*.py' -q`: 11 passed. Actual original receipts; fixed identity/source/run/hash/failure refusal; modified/escaping metadata; immutable clean qualified checkout; real ZIP artifact extraction/private-key/escape/link/size negatives; actual hashtag parsing; file-oracle save/backup/restore path and preservation; backup failure stops later capture; production modal hook captures only the exact confirmation and refuses repeated capture.
- `pwsh -NoProfile -File win/marketing/test_capture_helpers.ps1`: passed. Production C# RECT ABI, actual window plan, small owned-modal capture, 16 foreign/geometry/mutation refusals, failed-Add registration and unproven-process profile preservation.
- `pwsh -NoProfile -File win/marketing/test_display_modes.ps1`: passed. Production C# Unicode native structure/flag boundary, enumerated mode selection, test-before-apply, dynamic-only flags, restoration, failed-test preservation and partial-apply recovery.
- `python3 win/msix/test_installed_workflow.py -q`: 23 passed; unchanged qualified input/bytes/failure adapter suite. Its deliberately exercised CLI failure prints `chooser stayed open` while the test suite passes.
- `python3 win/msix/test_store_workflow_evidence.py -q`: 2 passed; unchanged complete saved/reopened/backup/restored/cleanup receipt validation and negative mutations.
- All new PowerShell files parsed successfully; Python compile and `git diff --check` passed.

Local PowerShell: `../../filequay/source/.tools/powershell-7.6.6/pwsh`; macOS temporary fixtures use `TMPDIR=/private/tmp`. Native API structures compile locally, but desktop changes, installed input, actual pixels and final lifecycle require the fresh Windows capture workflow. No new screenshots or capture success are claimed from these fixtures.

## Handoff

Root reviews, publishes the capture-helper commit and dispatches `marketing-screenshots.yml`. Review the three raw PNGs and require the separate `capture-result.json` success/cleanup evidence before adding them to the site or Store listing. Original validated product MSIX remains pinned and unchanged. No push, parent status, site edit or Partner Center action was performed here.
