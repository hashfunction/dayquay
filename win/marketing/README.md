# Real Jotmorrow marketing captures

Dispatch `.github/workflows/marketing-screenshots.yml` after review. It downloads the existing unsigned Store MSIX and qualification metadata from run `34681664116`, public source `64e8174c5f375fecf45539594b6a6b4beac8e025`. It never rebuilds the product. The binary is exactly `Jotmorrow_1.0.1.0_x64.msix`, 39,743,804 bytes, SHA-256 `47b1b5153eedbbf4709ff8dd143164ff90445009137682722da4951e13b066fe`.

The new workflow fetches artifact IDs `10294266549` (Store unsigned) and `10294785652` (native qualification), checks the original successful run, receipt hashes, complete unsigned container and immutable clean qualified checkout, then installs an ephemeral signed copy. The original unsigned file remains unchanged.

An exclusive owned profile holds ordinary preferences: Segoe UI 14, a 300-pixel sidebar, and a 1440 by 900 native main window. The helper selects an enumerated 1920 by 1080, 32-bit display mode with native test-before-apply and dynamic changes only, then restores the original mode. Screenshots require the actual 96-DPI window and complete visible bounds.

The installed app receives an original dated entry and real `#weekend`, `#ideas` and `#gratitude` tags through the exact qualified source's owned-window Win32 SendInput adapter. The helper captures three unmodified native frames:

1. `01-journal-entry.png`: the filled, saved current-day journal.
2. `02-restore-preview.png`: the actual portable-backup confirmation over that journal, before confirmation.
3. `03-restored-journal.png`: the restored entry after the real backup and restore byte oracles prove equality and preservation.

Only PNGs and JSON capture receipts upload. Native screenshots are recorded as full main-window pixel captures, including the owned modal dialog where appropriate; there is no resizing, compositing, renderer emulation or pixel editing. Full installed payload hashes, packaged runtime modules, retained process/package identity and foreground/window bounds remain checked. Normal zero close, uninstall, profile ownership, certificate/private-key cleanup and display restoration must all succeed for `capture-result.json` to say `captured: true`.

The result explicitly claims no new product qualification, binary change, Store submission or certification change. The original qualification and already validated Store package remain separate. Current Windows execution and visual review are still required before using the screenshots.

Regression commands from this source root:

```text
python -m unittest discover -s win/marketing -p 'test_*.py' -v
pwsh -NoProfile -File win/marketing/test_capture_helpers.ps1
pwsh -NoProfile -File win/marketing/test_display_modes.ps1
```

`fixtures/original-receipts.json` retains actual original successful receipts solely for read-only validator regression. Local UI/frame/ZIP fixtures are explicitly synthetic and cannot create qualifying screenshots.

Capture input regression: [newline-repair-review.md](newline-repair-review.md) documents native run 34684051917 and the capture-only ordinary Enter route. Run capture Python tests with the hash-pinned host serializer dependency from `requirements-test.txt`; the workflow installs it only into its temporary test environment. Product and qualification binaries remain unchanged.
