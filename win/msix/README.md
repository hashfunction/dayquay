# DayQuay disposable MSIX qualification

This helper qualifies a temporary x64 package from the real PyInstaller
`dist/DayQuay` stage. It does not supply a production Store identity or qualify
journal backup/restore, upgrades, WACK, native source delivery or public release.
No application behavior or native dependency selections change.

The approved plan is `microsoft-store/docs/plans/dayquay-msix-qualification.md`
in the parent portfolio. Source baseline: `ffcfdeb93f6fd60af19c1ac9656aef76ba4a1468`.
The implementation adapts TwinQuay `1ee1e1849ad2aad030717b7ba56254197436ea4e`,
PixelQuay `b7672df853a9e182ed1b081c03ab800dc3dbc778`, ReticleQuay, and FileQuay's
retained-process observation pattern. The MIT notices are retained alongside the
helpers. The combined DayQuay application remains GPL-3.0-or-later, with original
copyright and license files preserved.

## Inputs and package boundary

`win/record-package-inventory.py` runs in the same MSYS2 UCRT64 Python used for the
native build, after the unchanged PyInstaller spec and before native startup.
It records every stage file, preserves installed native notices and available
PyEnchant distribution notices, records the exact interpreter path/hash, and
binds source notices, artwork, GTK UI title/resources, spec, hooks and dependency
metadata. The native startup receipt now requires exact `DayQuay`, this source
commit, executable hash and complete inventory hash. Replacing previous receipts
is refused.

The native input check rehashes the entire downloaded package cache, compares
installed/downloaded package versions, and checks the direct versions/archive
hashes in `win/windows-dependencies.json`. The existing MSYS2 setup still resolves
rolling repositories; a drift from those source-qualified direct inputs fails
closed. There is no resolver update, package override or claim that the rolling
setup is reproducible. PyEnchant retains its existing hash-required source install.

The actual UCRT runtime contract is `libpython3.14.dll`, GTK3, GtkSource4,
`bin/libenchant-2-2.dll`, its `lib/enchant-2` Hunspell provider and one
unambiguous PyGObject `_gi*.pyd`. The `bin` layout preserves PyEnchant 3.3's
relocatable-prefix calculation, while the early runtime hook prepends the
packaged `share` directory to GLib's system data search for the bundled en_US
dictionary. Required typelibs,
source resources and dictionaries are separately inventoried. No CPython.org,
Qt or .NET application paths are substituted. Transformed Python/bootloader build
output is not represented as byte-identical to upstream package archives.

Fixed temporary identity:

- `Trieflow.DayQuay.Qualification`, `CN=DayQuay-CI-Qualification`, `1.0.0.0`, x64.
- Application `DayQuay`, executable `DayQuay.exe`, one `runFullTrust` capability.
- Windows.Desktop minimum `10.0.19041.0`, tested manifest maximum `10.0.26100.0`.
- Original DayQuay PNG-derived package assets; no associations or protocol entries.

Windows SDK `10.0.26100.0/x64` MakeAppx is hashed before/after semantic `/v /h SHA256`
pack and unpack. No `/nv` or overwrite flag is used. Independent XML, ZIP/OPC and
unpacked inventories must match every payload byte, identity field, asset and
membership. Installation rechecks current clean source, inputs, package and the
entire installed payload, allowing only the known SDK/signature metadata extras.

## Installation and evidence

The installer refuses existing matching registrations and existing DayQuay/legacy
host profiles. It signs only a temporary copy using a nonexportable ephemeral key,
trusts only that public certificate and verifies the exact signer/SignTool hashes.
Ownership of a registration starts only after this invocation's successful Add
and one exact expected x64 registration. A failed Add never authorizes cleanup of
a matching package that raced into view.

Broker activation uses the exact AUMID. Before process cleanup ownership is
claimed, the helper retains its live handle and verifies the installed executable,
its bytes and `GetPackageFullName`. Required modules must be loaded from the exact
installed inventory. Other modules must be under Windows or the narrow, valid
Microsoft-signed Defender `Platform/<version>/MpOav.dll` exception retained from
TwinQuay's native evidence; an arbitrary MSYS2 runner DLL cannot satisfy a module.

The exact source-derived `DayQuay - <localized date>` title must survive a stable interval. UI evidence
requires the owned visible window, bounded UIA tree and screenshot, foreground
ownership, nonuniform pixels and no unexpected/error/modal top-level surface.
GTK3 may expose only its window to UIA. The record explicitly distinguishes this
limited startup observation from exposed actionable controls; neither counts as
journal/backup/restore acceptance. The helper injects no journal or preference
state. Normal close must yield an observed zero exit. Forced termination is
failure cleanup only, through the already-owned live process handle.

Cleanup removes only the captured full package name, the invocation's certificate
entries and its successfully created signing directory. Creation failure never
confers temporary-directory ownership. Primary, cleanup and final reporting
failures are retained separately; existing evidence bytes are never replaced.
New app-created profile data is not broadly deleted by this helper. CI is a fresh
disposable runner; profiles, binaries, packages, certificates and keys are excluded
from public artifacts.

`build-evidence/msix-package-record.json` and `build-evidence/msix-install/` contain
bounded JSON/text/PNG metadata only. An installation pass is conditional on every
operation, cleanup and final unsigned-package hash check. The records keep
workflow, native-source, upgrade, WACK, Store identity and public-release flags
false. Native notice collection is not full license or corresponding-source
clearance; those remain explicit unresolved release gates.

## Commands and local validation

On the existing disposable Windows workflow, after native tests/PyInstaller:

```text
python win/record-package-inventory.py
pwsh -NoLogo -NoProfile -File win/test-native-startup.ps1
pwsh -NoLogo -NoProfile -File win/msix/qualify-msix.ps1
```

`qualify-msix.ps1` reads the exact same-run MSYS2 Python record. It does not resolve
an ambiguous `Get-Command python` list or guess a virtual environment path.
The workflow runs fixture tests before building/package installation and uploads
only explicit metadata globs. The 30-minute native job and 10-minute MSIX step
are bounded; a runner timeout or missing diagnostic never counts as cleanup or
qualification success.

Development evidence on the locked Mac:

- RED: 23 package tests failed before the module existed; three real-file notice
  tests failed before collection existed; registration tests lacked the installer.
- RED: the GTK-specific window fixture rejected the copied Qt More Options rule.
- RED: the real preparation/cleanup closure deleted a simulated unowned directory
  when creation failed. Assigning ownership after successful creation fixes it.
- GREEN: 23 Python source/stage/receipt/runtime/notice/XML/ZIP/SDK tests and three
  native notice-copy tests. These use real files/ZIPs; SDK execution is a fixture.
- GREEN: seven PowerShell suites: six orchestration scenarios, five reporting
  scenarios, nine real registration-closure flows, five real process/cleanup
  checks, GTK positive plus nine rejection variants, three Defender metadata
  controls plus 16 rejection cases, and the real temporary-ownership regression.
  Appx/signature/UI adapters in local fixtures do not claim Windows runtime success.
- GREEN: 70 existing backup/restore/product/Windows-build-helper application tests.
  Full test collection still has four `No module named gi` errors locally.
- GREEN: Python syntax, Black formatting, PowerShell parsing, embedded native C#
  compilation, workflow YAML and metadata-only artifact inspection, diff checks.
- Local toolchain: Python 3.10.11; PowerShell 7.6.6 on .NET 10.0.12. No local GUI,
  Windows SDK pack/install/broker execution, external publish or account action.

Prior Windows run `34579114265` (public source
`633edcb521a7abfca62f8e355908dfcfa5a22eae`) passed 156 application tests with three
skips, actual GTK/spellcheck imports, PyInstaller and the native DayQuay main
window. Its actual compiler log identified `libpython3.14.dll`. It predates these
MSIX helpers and does not qualify their installation path. Independent review
and a fresh exact-source Windows run remain required, followed by the separate
journal/backup/restore, accessibility/DPI, upgrade, WACK, source/license delivery
and Store gates.


## Independent review repairs against 1311e9e

The real `Journal.set_frame_title()` supersedes the initial bare `DayQuay` title.
Retained Windows run34579114265 proves `DayQuay - Friday, 9/11/2026`. The new
`window_title_contract.py` checks the reviewed production method/default format
structurally, then executes that actual method with the actual date formatter and
a fresh default journal (`data`). This qualification-only extraction imports no
GTK or profile data and changes no product source. The helper retains the
upstream method copyright under GPL-2.0-or-later.

Before the native launch, the exact recorded MSYS2 Python initializes the same
user-preferred locale as the application and exclusively writes an exact
expected-title/date/locale contract. The receipt binds this contract plus the
observed title; the package record carries it after source/stage verification.
Journal, default configuration, formatter, localization and helper source hashes
are included in the input inventory. Install preflight recreates the expected
contract from current source/date/locale. The native startup and broker wait for
the exact stable title within their unchanged existing budgets, then recheck it
after three seconds. UIA, visible top-level windows and screenshot observations
use that same exact title. Bare/transient titles, prefixes, suffixes, whitespace,
error variants or coherently changed contract fields do not qualify. A locale or
date boundary requires fresh observations; the comparison is never widened.

Install preflight now requires `unpackedVerification` to contain exactly one
integer `verifiedPayloadFiles`, equal to the complete source-derived payload
count. The actual MakeAppx unpack step remains the operation creating that
record; local ZIP fixtures do not establish native SDK execution.

If Add returns successfully but exact registration ownership is never observed,
cleanup reports uncertainty even after two empty queries. It preserves any
unowned registrations and the primary observation failure. An empty residue
list is no longer presented without an accompanying cleanup error in this case.

RED/GREEN evidence:

- The actual extracted journal method and formatter generated a dated title,
  and the prior receipt validator rejected it. It now passes. Mutation coverage
  also rejects changes to the actual method/default date format and coherent
  title-contract tampering. The real helper subprocess refuses prior output.
- Eight missing/empty/zero/wrong-type/wrong-count/extra-field unpack variants were
  incorrectly accepted; all are now rejected. A correctly unpacked fixture passes.
- The actual Install/RemoveOwnedPackage closures with successful Add and no
  observable registration omitted uncertainty; they now retain primary plus
  cleanup errors and call no removal operation.
- Final GREEN: 27 package/title tests, three native-notice tests, all seven
  PowerShell suites (now ten registration cases), 70 unchanged focused application
  tests, ten PowerShell AST parses, Python compile/Black and `git diff --check`.
  PowerShell fixtures run in separate processes, matching CI; a local attempt to
  run all fixtures inside one shared shell exposed fixture function-scope
  interference, not a product failure, and was replaced by the actual CI method.

No Windows GUI, SDK pack/unpack, installed broker activation, normal close or
owned uninstall result is claimed for these changes. Root owns independent
re-review and fresh exact-source Windows qualification. No dependency selection,
application behavior, workflow file, account or public-release state changed.


## Native junction fixture repair after run34613988830

At source7ea423e, the actual MSYS2 UCRT Python3.14 runner passed26 package
tests but `cmd /d /c mklink /J` exited1 before the junction assertion. Its
recorded operands were `D:/a/_temp/msys64/tmp/.../release/redirect` and
`D:/a/_temp/msys64/tmp/.../external`; the captured native diagnostic was not
printed by CalledProcessError. The previously qualified TwinQuay counterpart
uses native CPython Windows Path spelling. This evidence motivates normalizing
only these test operands to Windows backslashes; the next native run must
confirm the repaired command on MSYS2.

The fixture still executes real `mklink /J` on Windows, now with spaced directory
names to exercise subprocess argument quoting, `/d` to disable AutoRun and
`/v:off` to disable delayed expansion. Test-owned paths containing command
syntax/expansion or control characters are rejected before invocation. A nonzero
exit fails the test with the exact operand list and captured stdout/stderr; it
never skips. After creation, native lstat must prove the reparse attribute and
mount-point tag before the unchanged real stage validator rejects it. Cleanup
removes the link itself in finally, without following it. Production reparse
rejection and package behavior are unchanged.

Microsoft primary command references: [mklink](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/mklink)
and [cmd quoting/options](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/cmd).

RED: the extracted original command seam retained the exact forward-slash
fixture operands, failing the native-path assertion. Diagnostic and unsafe-path
regressions also failed before repair. GREEN: all30 package tests and3notice
tests pass locally, including the actual POSIX directory-link rejection and
three added command/diagnostic/syntax regressions. Black100 and diff checks pass.
Local command-adapter tests do not execute cmd.exe or claim a native junction
pass. Independent source review and fresh exact-source Windows qualification
remain required. InkQuay uses direct CreateSymbolicLinkW/RemoveDirectoryW test
APIs, so its qualifier confirmed this specific cmd operand issue does not apply.

## Notice fixture follow-up after run34615894079

Run [34615894079](https://github.com/hashfunction/dayquay/actions/runs/34615894079)
at source `7aeaf054919d869ff8e2920f3250b48d2b771157`, public snapshot
`853660cc449b7939f0e909ec84ffeb6a8ce59acf`, passed all 30 package tests in
18.749s. This includes the actual Windows junction creation, native reparse-tag
assertion and unchanged stage rejection: the preceding junction repair passed
on the MSYS2 Python3.14.7 runner. The following notice suite failed in its
separate, still-old `cmd /d /c mklink /J` invocation with `D:/...` operands,
before it could test notice rejection. The other two notice tests passed.

Both suites now inherit the same test-only Windows junction helper. Its native
path conversion, quoting, command-syntax rejection and failure diagnostics are
unchanged from the qualified package fixture. The notice test uses a spaced
link path, verifies the native mount-point reparse tag and removes the link in
`finally`; the real notice collector must still reject it, leaving no notice
output. There is no skip or alternate success path, and production collection,
package gates, application behavior and workflow are unchanged.

The new regression calls the notice fixture's actual Windows link-creation
method with the observed MSYS path shape and captures only the subprocess
boundary. RED retained the old `/` operands and command options; GREEN uses the
shared native command. All 30 package tests and four notice tests pass locally,
as do Black100 and diff checks. Local tests exercise real POSIX notice rejection
and Windows command construction; the repaired Windows notice fixture still
requires a fresh native run. Failed-job log SHA256:
`a7c375c099a9c4dd36a177a57b2b06a9c8799160f95c79ad7b7408d0807e2d0d`.

### Native Git input

Run 34617485484 passed both junction suites and the native application build,
then failed before stage collection because MSYS2's native Python could not
launch Git. Git is now an explicit MSYS2 build input, recorded with the rest of
the installed packages. Before building, the workflow executes Git through that
same Python, checks the current commit and requires a clean checkout. Tracked
text uses LF under both Git for Windows and MSYS Git; binary bytes are unchanged.
A real clone regression proves stable bytes/clean status under both defaults and
continued rejection of actual source and binary changes. Native confirmation
and downstream startup/MSIX execution still require a fresh run.

## Complete-window screenshot placement after run 34639820548

At application source `2231eb9fde283053e65a70c4065a41394a0d5311` / public
snapshot `ac617f5a0f99923eeac3e052e244860f1a8d86ad`, the actual installed
broker process loaded the packaged Enchant broker, Hunspell provider and
Hunspell DLL. The preceding native startup log listed `en_US` and its Hunspell
dictionary. Its exact date-title window was visible at 1040×739, with a single
GTK UIA root. The screenshot observer rejected it as outside the visible
desktop; the old evidence did not retain x/y or desktop dimensions, so it cannot
distinguish an oversized window from offscreen placement. No screenshot or
normal-close success is claimed from that run.

The observer now restores/focuses the same verified owned HWND, observes its
actual monitor work area, and moves/resizes it only when the entire window does
not fit. It retains the original geometry, requested geometry and fresh observed
geometry, including the virtual desktop. The move uses SetWindowPos with
ASYNCWINDOWPOS/NOACTIVATE/NOZORDER; a maximum twenty 250ms observations must prove
completion. Each observation and the immediate move boundary verify the same
live process/HWND/PID. The exact title, visibility, full work-area containment,
400×300 minimum/8192 maximum, foreground ownership, full-desktop containment and
nonblank screenshot checks remain mandatory. A refused minimum size, a native
error, changed identity/title or insufficient desktop still fails; requested
coordinates never substitute for observed coordinates. Consumer source and
packaged runtime gates are unchanged.

Local PowerShell tests execute the actual placement operation with an oversized
window and fourteen fit/foreign/title/hidden/negative-monitor/nonfinite/refusal
cases, compile the native declaration and verify production capture wiring.
Existing nine screenshot-policy negatives and eight title variants still fail.
These tests adapt only the native observation/move/wait boundaries; actual
Win32 placement, screenshot, normal close and complete qualification require
the fresh exact-source Windows run.

Primary API references: [SetWindowPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos)
and [Screen.WorkingArea](https://learn.microsoft.com/en-us/dotnet/api/system.windows.forms.screen.workingarea?view=windowsdesktop-10.0).

## Original notice supplement — source delivery follow-up

The existing post-build collector now carries `win/notice-supplement` into
`_internal/notices/supplement`. It contains 648 original files, 3,384,225 bytes:
643 Cargo notice/license texts plus 5 upstream originals. Existing installed
native/PyEnchant collections and all earlier source license texts are retained.
The 480,295-byte index has SHA256
`504ce4ea01ad8fc92dd9fa53660fa5f677b9eb51547004ba45ea52dc1b8f94e8`;
it names every copied byte hash and original archive/member, the exact librsvg
resolved lock, source inventory run 34642181739 and frozen source-delivery
manifest SHA256 `63cab5ab45105a57d95f7d6215d8777495acfb4dacbf3a939ddb8cb15bc4697f`.
The index includes all 359 Cargo registry inputs, including build/test/proc-macro
inputs; it does not claim all those packages are linked into the application.

Collection validates the checked-in index before creating its output, uses
exclusive writes and rechecks both source and destination afterward. Existing
source-to-stage verification now requires the whole original tree, including
the index. Updating a receipt cannot hide a missing or altered packaged copy.
The source subtree uses Git `-text`; original CRLF and other upstream bytes must
survive both Git for Windows and MSYS Git unchanged. See `win/README.txt` and
https://dayquay.trieflow.com/source for the corresponding-source build/delivery
instructions. No dependency selection, recipe, runtime hook, product behavior,
workflow, package identity or lifecycle gate changed.

RED was observed in the actual collector (supplement absent) and a real Git
clone (CRLF changed to LF before the attribute rule). The new package regression
also fails when only the supplement source-binding entry is removed: both
missing and corrupted copies become accepted after receipt regeneration.
GREEN verification covers original byte copies, missing/corrupt/unindexed and
mistyped inputs, injected corruption during copying, preservation of unrelated
stage files, refreshed-receipt rejection and actual checkout byte preservation.
The focused suites are `test_native_notices.py` (7 tests),
`test_msix_qualification.py` (33 tests), and `test_source_checkout.py` (1 test).
They use real files/archives and actual qualification methods; these local
checks do not qualify a newly built Windows package. Root owns independent
review and the exact-source native build/installed qualification.

## Installed journal/backup/restore qualification

Windows run [34650691200](https://github.com/hashfunction/dayquay/actions/runs/34650691200)
passed the complete native package, installed identity, 183-module runtime,
screenshot, normal-close, uninstall and cleanup qualification at source
`a931ae3e017f38e9b27952339d494d527b45db41`. Its actual UI Automation tree
contained only the owned top-level `ControlType.Window`: zero actionable
controls were exposed. The receipt therefore correctly left
`journal_backup_restore_workflow_tested=false`.

`installed_workflow_qualification.py` now uses bounded Win32 `SendInput`
keyboard/mouse events against that already-verified foreground process and
exact main HWND. It clicks the visible editor, replaces its content with a
unique synthetic sentinel and invokes the real Save action. It then switches
through the real New Journal UI to an empty owned journal, observes the changed
window title, reopens the original through the real Open dialog, appends a
second marker in the editor and saves it. It creates a portable backup through
the Journal menu and Save chooser, and drives the existing restore inspection,
fresh-folder and Open-restored-journal dialogs. Before every input packet, the
helper rechecks its retained process handle plus the exact visible, enabled,
owned foreground HWND and title. A missing or unexpected dialog, changed or
closed PID/HWND, lost foreground, refused path, timeout or error fails the
qualification before further input is sent.

Independent checks capture the exact saved month bytes and require the same
file name, byte count and SHA-256 after reopening, inside the backup manifest
and ZIP payload, and under the newly restored journal path. The restored main
window must carry the exact source-derived title for that fresh folder. After
restore, the original journal tree and backup archive are hashed again and must
still match their protected pre-restore bytes. No product API, alternate
executable argument, hidden command, or test-only consumer behavior is used.

The runner must begin without either the DayQuay or legacy RedNotebook profile.
Qualification exclusively creates `%APPDATA%\DayQuay`, records an unpredictable
ownership marker, uses only its default `data` journal and fresh restore folder,
and removes it only after the verified owned process stops. A pre-existing
profile, changed marker, reparse path, incomplete construction cleanup or
unproven process shutdown is preserved and fails cleanup rather than being
removed. Existing package identity, complete installed payload, module,
Defender-signature, screenshot, process-handle, normal-close, registration,
uninstall, certificate and temporary-directory gates remain required.

The local regression exercises the full save/reopen/backup/restore verifier and
rejects no-op reopen, lost/replaced input targets, stopped processes, changed
archive bytes, deleted/changed/extra original files, extra restored files,
missing/wrong markers and invalid title contracts. The Windows workflow also
runs real profile ownership and orchestration tests, including partial-build,
reparse replacement and unproven-shutdown preservation, before packaging.
macOS cannot execute Win32 input, GTK Windows dialogs, PowerShell, MSIX
installation or native cleanup; a fresh reviewed Windows run remains the
required acceptance evidence.
