# Jotmorrow first screenshot status

Base: `378cc47a0324384671bb2241627d9408d3108795`. Successful native marketing run `34685283671` produced three real images and completed normal zero-exit close, uninstall and cleanup with the unchanged validated package. The inspected `01-journal-entry.png` shows the real entry and a saved-location status containing the compatibility directory `AppData/Roaming/DayQuay/data`. The other two images already show the application's `Nothing to save` status.

The capture-only change performs a second ordinary Save after the original persisted-month proof. The unmodified `Journal.save_to_disk` implementation calls `storage.save_months_to_disk`; an unchanged month returns false and follows the existing `Nothing to save` message branch. The second Save uses the same original owned native Ctrl+S path. The existing protected-journal oracle then checks that the month file bytes remain identical before the first screenshot.

Only `win/marketing/capture_ui.py`, its sequence fixture and this report change. No pixel editing, data-path change, product preference/behavior change, package change, qualification change or other aesthetic adjustment is included. The legacy journal directory remains compatible.

The focused sequence fixture now uses one real retained Month through `storage.save_months_to_disk`: the first save returns true and the unchanged second save returns false. A separate ordering/refusal case proves the second Save occurs after persisted-byte verification and that changed journal bytes prevent the screenshot. The updated tests failed against the old one-save sequence and passed after the capture-only adjustment.

Validation:

```text
PYTHONPATH=/private/tmp/jotmorrow-capture-test-pyyaml603 ../../twinquay/source/env-qt6/bin/python -m unittest discover -s win/marketing -p 'test_*.py' -v
# 16 passed
git diff --check
# passed
```

A fresh Windows marketing run must confirm the actual first image now shows `Nothing to save`. The existing successful images were not modified. No push, site, Store or parent-status edit was performed.
