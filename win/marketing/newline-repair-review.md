# Jotmorrow marketing newline input repair

Base: `d7a0f0845c6a90abd5cad7d892200bf2ac0cdf17`. Evidence: actual capture run `34684051917`, public capture source `a8def737`; unchanged qualified package/run `64e8174c5f375fecf45539594b6a6b4beac8e025` / `34681664116`.

The first inspection was the complete `journal-capture-failure.json` and native `failure-window.png` from `/private/tmp/jotmorrow-marketing-34684051917-review/Jotmorrow-real-product-screenshots`. The image shows the full fictional entry merged into one paragraph in the intended editor. Native focus, foreground and retained input target all identify its owned `gdkWindowToplevel`. The saved month is 825 bytes, SHA-256 `0cf99b6cb42f1ff3e2f4b689a4d652e79e74773a96c030f02b23f58584342385`.

Loading that actual saved month through the product's real storage loader proves the precise fault: its 774-character entry equals the intended 797-character entry with all 23 LF characters removed. Every other character is intact. The original generic Unicode `SendInput` route encodes LF as `KEYEVENTF_UNICODE` with scan value 10; the observed GTK editor discarded those packets. YAML then wrapped the resulting long paragraph across the required marker. This was an input line-break problem, with YAML folding explaining the subsequent raw-marker failure.

The repair is an eight-line marketing-only override of editor replacement. It preserves the original owned foreground/editor click and Ctrl+A sequence, sends each nonempty line through the original Unicode text method, and sends every intervening LF through the existing ordinary Enter key method. Blank paragraphs and the trailing LF are retained. Every text/Enter batch continues through the original final `_send` ownership, exact foreground/PID and complete-native-input checks. Original application/runtime, qualification helpers, markers, backup/restoration byte checks, protected-file checks and lifecycle cleanup are unchanged.

Regression coverage:

- The retained fictional diagnostic JSON is an actual native failure fixture. Its recorded length and SHA are checked before decoding it with the real product loader.
- The original native INPUT encoder plus the observed GTK LF behavior reproduces the actual 825-byte saved YAML exactly using production `_save_month_to_disk` and PyYAML 6.0.3/LibYAML.
- The fixed production capture class sends exactly 23 ordinary Return key-downs and zero LF Unicode packets. Its output is exactly the original entry, including blank lines. The real month serializer/loader preserves it, discovers all three real hashtags, and passes the original saved/protected journal oracles.
- A foreground ownership change before Enter stops before the next native call. A partial Enter batch raises the native failure and stops before later text; neither condition is retried or bypassed.
- Existing capture backup/restore sequence fixtures now write through the real product month serializer instead of a raw text-file stand-in. Their archive and restored/protected byte checks remain active.

Validation completed locally:

```text
PYTHONPATH=/private/tmp/jotmorrow-capture-test-pyyaml603 ../../twinquay/source/env-qt6/bin/python -m unittest discover -s win/marketing -p 'test_*.py' -v
# 15 passed
PYTHONPATH=/private/tmp/jotmorrow-capture-test-pyyaml603 ../../twinquay/source/env-qt6/bin/python win/msix/test_installed_workflow.py -v
# 23 unchanged tests passed
```

The new test first failed against the old marketing input route, while its recorded-native-failure and old-route reproduction controls passed. The fixed route then passed. The partial-input replay mocks the Windows error constructor on macOS, while executing the unchanged production send boundary.

The capture workflow installs only a hash-pinned PyYAML 6.0.3 test wheel (154,003 bytes on CPython 3.12 Windows x64) in a temporary host test dependency directory. This matches the qualified MSYS2 `python-yaml-6.0.3-3` package's upstream version. It is not copied into the app, loaded by the capture driver, or added to its unsigned MSIX. Its hash comes from the PyPI 6.0.3 release metadata. The separate macOS arm64 wheel is pinned for this local replay; existing Python 3.12 at `../../twinquay/source/env-qt6/bin/python` was used with the isolated `/private/tmp` dependency path.

The native Windows rerun remains required. No new marketing image has been generated locally, and this repair does not alter the already validated Store package, its qualification outcome or any submission/site/status. No push was performed.
