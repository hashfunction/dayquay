# DayQuay fixed Store identity and source-bound unsigned export

This candidate adds release tooling only. It keeps the current customer-facing
branding and the approved immutable package identity. Final marketing captures
are held while the product's new distinct name is being reserved. No Store
submission, public binary release, site update, or parent release-status change
is part of this candidate.

## Actual Windows evidence used for the source comparison

Run `34676387900` succeeded at public application commit
`581ca61286f85496bee30e6c7d43bce2ed801d93`, corresponding to local application
source `71f546bae46c6ca02a338a680a5a406d66ab1f8a`. Its complete native and
installed-consumer artifacts were reviewed locally from the retained
`DayQuay-native-qualification` artifact.

The actual installed consumer saved a 72-byte journal, opened another journal
and returned, appended and saved a 130-byte journal, created a 577-byte ZIP,
restored the exact journal into a fresh destination, and preserved both the
original journal and original ZIP. The retained broker-activated process exited
normally with code 0. Exact registration removal and owned profile cleanup
passed. The disposable package SHA-256 was
`03deaa8c720a4d8ae713a81f7a704b2ee8fe974e93f894303a0d8cffcd33b66c`;
the application executable SHA-256 was
`82b2bde79c7c5f8c545d6b3a3e6c03474a9fcf4869de21b0538b31c0cf9c61b5`.

This successful run qualified the disposable identity. It did not qualify the
Store identity or this new export implementation. Neither local test fixtures
nor this report substitute for that pending Windows run.

## Corresponding-source and notice comparison

The unchanged native inputs are covered by the already published collection:

- Release: <https://github.com/hashfunction/dayquay/releases/tag/native-sources-2026-09-11-df058>
- Source archive: `dayquay-native-sources-df058.tar`, 483,645,440 bytes,
  SHA-256 `01555441371a207b2d97bb9835bc26a34d89056382d2cada58d29d508bc69ee0`.
- Manifest: `source-manifest.json`, 389,430 bytes,
  SHA-256 `63cab5ab45105a57d95f7d6215d8777495acfb4dacbf3a939ddb8cb15bc4697f`.
- Source-basis native run `34642181739`, public application source
  `7ac167ef421f33a3475a5c41fb1de268e1678adc`.

The retained full TAR and every one of its 1,572 regular members were streamed
and verified without extracting another checkout. The 424 source archives
comprise 64 MSYS2 source packages, PyEnchant source, and 359 Cargo crate sources;
1,147 metadata entries plus the manifest complete the archive. The current
public GitHub release asset sizes and digests matched these retained bytes.
The prior source collection includes original package recipes, source inputs,
patches, the librsvg lock after recipe processing and Cargo sources, and the
required winpthreads source. It does not claim bit-for-bit reproduction of
vendor binaries.

The comparison of that source-basis inventory with the successful Windows run
proved all 178 native archive hashes and all 89 installed versions unchanged.
All 1,165 mapped vendor file hashes also match. The older release tree grew from
1,323 to 1,972 files. Its only changed existing non-vendor files were the
application executable, frozen Python `base_library.zip`, and the top-level
third-party notice. The 649 additions are the supplemental notice index and
648 original notice files, whose exact hashes are present in the published
source collection. All 117 prior notice payload files are unchanged. Thus the
new descriptor binds all 766 original notice payload files.

All 687 recorded production/build source inputs in the successful run still
match current source. These 687 inputs are the existing packager's explicit
source inventory, not a claim that every Git file is listed there. The export
gate separately binds the entire clean source checkout and its Git tree to the
explicitly reviewed public commit, including the new qualification tooling.

`native-source-publication.json` records the exact archive/version/vendor/notice
maps and their audit provenance. `source_publication.py` fails closed when any
of those inputs change. A subsequent MSYS2 update requires a new source audit;
it cannot reuse this descriptor merely because qualification passes.

The existing historical unresolved-notice and `licenseClearanceClaimed=false`
packaging fields remain intact. This candidate proves source availability and
unchanged audited bytes; it does not invent a frozen Python module inventory,
claim vendor binary reproducibility, or declare Microsoft certification.

## Fixed identity and full installed workflow

Only two modes are permitted. The original qualification identity remains the
default. Store mode uses the independently recorded Partner Center identity:

- Name `1659hashfunction.DayQuay`
- Publisher `CN=B6A2631A-FD32-45CC-AE12-82466975F528`
- Publisher display name `hashfunction`
- Package family `1659hashfunction.DayQuay_r3hxytd7jt6c4`
- Version `1.0.0.0`, x64, application `DayQuay`, executable `DayQuay.exe`

Manifest creation, strict manifest/container/installed-tree validation, package
record validation, temporary signing, registration ownership, and activation
all use the same selected fixed mode. Arbitrary package identities and
cross-mode package records are rejected. The workflow sequentially packages
and installs both identities; each executes the full existing journal/tag,
reopen, backup, restore, protected-original, normal-close, uninstall, and
marker-owned profile cleanup flow. Each installation receives an exclusively
created fresh profile after the prior owned process has stopped and cleanup
has completed. No input method, UI selector, acceptance gate, timeout, or
product behavior changed.

Receipts now include the workflow run and attempt. The installed workflow also
records its actual helper hash, and the existing window observation records
the main HWND for cross-checking against the retained consumer process.

## Unsigned export gate

A push still retains metadata only. Explicit `workflow_dispatch` inputs
`export_store_package=true` and `reviewed_public_source=<exact reviewed commit>`
request a retained unsigned package. This is preparation for review; dispatch
and publication remain the root task's responsibility.

`export_store_package.py` requires the disposable Windows workflow, exact
repository, clean committed source and public Git tree, and an explicitly
reviewed commit equal to the run's source. It verifies:

1. The complete current application stage, source input inventory, native
   startup receipt, strict unsigned MSIX contents, and SDK unpack receipt.
2. The exact Store identity, unsigned input hash, installed executable hash,
   retained PID/HWND, screenshot hash, native runtime module hashes, source,
   workflow run, and attempt across standalone and final receipts.
3. Saved and reopened month files, independently observed journal transitions,
   appended marker, exact restored and protected original file sets, original
   ZIP preservation, and both normal-exit observations. All original install,
   uninstall, profile, certificate, and evidence cleanup requirements must pass.
4. Exact native archive/version/vendor/notice maps against the reviewed source
   descriptor, the publicly available source manifest bytes and release asset
   digests, and the exact publicly available application commit/tree.
5. Unchanged source, stage, and all retained receipt bytes immediately before
   and after copying the unsigned package.

The output directory must be new with no reparse/link ancestors. Only the exact
verified unsigned MSIX is copied. `release-ready.json` is written last. On a
late failure, cleanup removes only files with the expected hashes from the
same created directory identity; foreign or changed output is preserved and
reported. The retained receipt states `submitted=false`,
`public_application_binary_released=false`, and
`store_certification_claimed=false`. Signed installation copies and private
certificate material are excluded from the export artifact.

## Verification

The new fixed-identity stage test was observed failing before the mode existed.
The new module-evidence mutation test exposed duplicate runtime records being
collapsed by a dictionary; validation now rejects duplicate packaged modules
and unknown module origins. The complete export test exercises real temporary
Git commits, actual stage reconstruction and ZIP verification, and independent
output hashes. Its service and installed-GUI receipts are explicitly synthetic
fixtures and make no native success claim.

Local verification passed: all 89 Python tests in 99.192 seconds; all eight
existing PowerShell fixture suites plus the new fixed-identity suite (20
changed records, two cross-mode records and arbitrary-mode refusal); changed
PowerShell parse checks; Python compilation; and `git diff --check`.

Commands:

```sh
python3 -m unittest discover -s win/msix -p 'test_*.py' -v
TMPDIR=/private/tmp /path/to/pwsh -NoLogo -NoProfile -File win/msix/test_store_identity.ps1
# Also run all eight existing PowerShell fixture scripts named in build-windows.yml.
git diff --check
```

The local macOS PowerShell profile fixture requires `TMPDIR=/private/tmp`:
its default `/var/...` temp path traverses the real `/var` symlink and is
correctly rejected by the unchanged ownership check. No check was disabled.

Windows execution of both identity modes and an explicitly reviewed export
remain pending. WACK, upgrade testing, final renamed branding, genuine
marketing captures, and Store submission are separate remaining release work.
