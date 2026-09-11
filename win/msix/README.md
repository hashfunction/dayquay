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

The actual UCRT runtime contract is `libpython3.14.dll`, GTK3, GtkSource4, Enchant,
its Hunspell provider and one unambiguous PyGObject `_gi*.pyd`. Required typelibs,
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
