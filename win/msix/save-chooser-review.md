# DayQuay SAVE filename selection correction

Baseline source `f0f43099fb479d8869d5ae89e551b0c7a0230b5b`, public snapshot
`7b50ee1a`, Windows run `34672751664`.

## Evidence and cause

The backslash directory chooser and journal reopen succeeded. The backup chooser
received the intended full native path, disappeared, and the independent ZIP
check then timed out because the exact expected archive was absent. The retained
Win32 observations do not expose GTK's filename text or its final selected path.
The screenshot helper correctly refused the stale chooser HWND after foreground
returned to the app. Thus this run alone does not prove where another ZIP was
written. Its failure receipt is at
`/private/tmp/dayquay-34672751664-review/msix-install/installed-consumer-workflow-failure.json`,
SHA256 `f695ed866d796f2243edcdf5faed983acad042183faeb2a95e63a0cc5b52bcff`.

`Backup._get_backup_file` first sets a name such as
`DayQuay-Backup-2026-09-12.zip`. `_select_path` previously sent Ctrl+L and typed
an entire filename/path without selecting the entire field. GTK 3.24.52's
SAVE-mode location handler focuses the existing filename entry; the entry's
focus override selects only the stem, retaining the final extension. GTK's
normal typing replaces the selection, leaving `.zip` after the newly typed path.
The relevant primary GTK sources are:

- [SAVE focus handling](https://github.com/GNOME/gtk/blob/3.24.52/gtk/gtkfilechooserwidget.c#L8139).
- [Filename selection excluding the extension](https://github.com/GNOME/gtk/blob/3.24.52/gtk/gtkfilechooserentry.c#L1037).
- [Ctrl+A whole-buffer binding](https://github.com/GNOME/gtk/blob/3.24.52/gtk/gtkentry.c#L2002).

A real local GTK 3.24.52 probe loaded only the unmodified `backup_dialog` Glade
subtree, set the same SAVE name, dispatched the chooser's Ctrl+L binding, and
observed selection `[0,25]` in a 29-character name. Replacing the selected text
using GTK editing APIs produced:

```text
selected_filename=<owned temporary directory>/DayQuay-consumer-backup.zip.zip
response=-5 filename=<owned temporary directory>/DayQuay-consumer-backup.zip.zip
```

Selecting the full entry before the same replacement produced exactly
`DayQuay-consumer-backup.zip`, including the actual OK response's selected path.
The chooser did not create an archive. Both temporary trees were removed and no
probe process remains. Source/log are retained at
`/private/tmp/dayquay-save-name-probe.c` and
`/private/tmp/dayquay-save-name-probe.log`; the log SHA256 is
`bf9d477dcf8e16e67259ab87569ac8cba2a5e9a215557e643bd5a1c5e26ca23b`.
This reproduces the GTK selection defect, while Windows-native Ctrl+A delivery
and the installed application's final archive remain for the next native run.
The local full-selection control used GtkEditable directly because the macOS
key theme differs; it is not evidence of Windows SendInput execution.

## Candidate

The installed workflow sends Ctrl+A after the owned Ctrl+L and before filename
text. It uses the existing retained-process/window/foreground-checked chord
method and records an `after_ctrl_a` observation. The Windows path spelling,
Enter/accept sequence, timeouts, independent archive content verification,
journal/tags/reopen/restore steps, normal-close and cleanup gates are preserved.
No application backup code, Glade, installer or workflow YAML is changed.

The separate existing Windows chooser probe adds two SAVE cases, using the exact
backup Glade, default name, Zip filter, and real `_WindowsInput` helper: the old
sequence and the sequence with Ctrl+A. It records entry selection/cursor/name,
selected filename, response ID, and exact target correspondence before/after
input. The original six folder cases remain. Both new cases use the same owned
probe process and marker-owned empty fixture tree; no ZIP/file is created and
these diagnostic cases cannot qualify the installed application.

## Verification

RED: the selection-aware workflow regression returned `backup.zip.zip`, and the
existing action-order checks proved that full selection was absent. GREEN:
23 installed-workflow and 11 chooser-probe tests pass, including the prefilled
extension case and refusal to type after ownership changes before Ctrl+A.
The actual Glade SAVE subtree is compared intact and unsupported chooser IDs
are rejected. Native Win32 ownership/SendInput code is unchanged. All 75 packaging/workflow/notice/source/probe tests pass; Python compilation and diff checks also pass.

Commands from the source root:

```sh
python3 -m unittest discover -s win/msix -p 'test_*.py'
python3 -m py_compile win/msix/installed_workflow_qualification.py win/msix/gtk_chooser_diagnostic.py
git diff --check
```

For the retained local source probe, build with GTK 3.24.52 development files:
`cc /private/tmp/dayquay-save-name-probe.c -o /private/tmp/dayquay-save-name-probe $(pkg-config --cflags --libs gtk+-3.0)`.
Its two arguments are an XML `<interface>` containing the unchanged
`backup_dialog` subtree and an exclusively owned temporary output directory.
It observes GTK selected paths/OK responses without creating those output files.

Independent root review and a fresh Windows native run are still required. The
next receipt must show the exact archive, validated ZIP contents, restored
journal/tags, unchanged protected originals, normal app stop, and owned cleanup.
No public push, snapshot, site or release-status change is part of this candidate.
