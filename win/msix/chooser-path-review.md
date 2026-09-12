# Windows chooser path correction

Baseline: `5f167de4f2278a90a2eb313aa3a1f726e48fac8f`.
Evidence: Windows run `34671346702`, `gtk-chooser-diagnostic.json`, SHA256
`a18bd5f96adfd591bddc223f1744076576c431f4452fddb6264fa04ad13d08ac`.
The run records GTK `3.24.52`; its installed-package inventory records
`mingw-w64-ucrt-x86_64-glib2 2.90.0-1` and GTK `3.24.52-1`.

## Observed failure and source mechanism

All three independent standalone actions (native Enter, native Alt+O, and the
diagnostic-only `activate_default`) activate the exact `_OK` response button.
Enter also emits the entry's activation signal. No action emits a dialog response;
`selected_path` remains null. The entry contains
`D:/a/_temp/msys64/tmp/dayquay-chooser-probe-g8tabfsw/DayQuay/ReopenProbe`, while GTK's
current-folder result uses backslashes. Each recorded input target is the owned,
visible, enabled, foreground chooser. The probe reports successful owned cleanup.

GTK's entry implementation splits the filename component with
`strrchr(text, G_DIR_SEPARATOR)` in both completion refresh and
`_gtk_file_chooser_entry_get_file_part()`. GLib's Windows build defines that
separator as backslash. The observed forward-slash path therefore leaves the
entire absolute path in the filename component. See the exact
[GTK 3.24.52 entry source](https://github.com/GNOME/gtk/blob/3.24.52/gtk/gtkfilechooserentry.c#L930)
and [GLib 2.90.0 Windows separator definition](https://github.com/GNOME/glib/blob/2.90.0/meson.build#L1793).

The remainder explains the silent refusal by inference from the matching source:
GTK's `check_save_entry()` passes that component to
`g_file_get_child_for_display_name()`. The local-file implementation delegates to
`g_file_get_child()`, whose absolute-name precondition returns null without setting
the supplied error. GTK's error helper displays a dialog only for a non-null
error; its chooser response handler then suppresses acceptance of the malformed
entry. This matches the observed null selection, clicked OK, and absent response.
Sources: [GTK validation](https://github.com/GNOME/gtk/blob/3.24.52/gtk/gtkfilechooserwidget.c#L5985),
[GLib local child lookup](https://github.com/GNOME/glib/blob/2.90.0/gio/glocalfile.c#L561),
[GLib absolute-name precondition](https://github.com/GNOME/glib/blob/2.90.0/gio/gfile.c#L908),
[GTK response filter](https://github.com/GNOME/gtk/blob/3.24.52/gtk/gtkfilechooserdialog.c#L641).

## Candidate scope

`installed_workflow_qualification._WindowsInput._select_path()` converts forward
slashes to backslashes only in the text supplied to local Windows choosers. It
records both the original path and exact input spelling. General journal text,
generated fixture paths, application source, native dependencies, Glade, native
input events, ownership checks, timeouts, acceptance assertions, and cleanup keep
their existing behavior. This is qualification input formatting, with no product
behavior change.

The failure-only standalone probe compares native and forward-slash spellings
for each of the same three actions. Its native spelling calls the same conversion
as the installed helper. All cases still run in the exact owned probe process and
reuse the same marker-owned tree and native input checks. The existing workflow
YAML is unchanged, and standalone observations never qualify the installed app.

## Validation and remaining evidence

The regression was observed failing against the original input method: forward,
mixed, Unicode, and UNC cases sent the wrong spelling. It now exercises the real
method and verifies exact input text, retained original-path metadata, Ctrl+L,
Enter, window targeting, and absence waiting in order. Existing tests exercise the
unchanged fallback and timeout evidence. Additional cases reject foreign
foreground ownership before any input and verify that general text retains slash
characters and exact UTF-16 key units, including a supplementary Unicode character.
The standalone tests cover both path spellings and reuse of the installed helper.

The 40 package/native-notice boundary tests passed, followed by all 31 current
installed-workflow and standalone-probe tests. `git diff --check` passed.
macOS cannot execute the actual Win32 chooser. Root review and a new installed
Windows workflow run are required to establish that this candidate clears the
original failure and reaches the remaining journal, backup, and restore checks.
If qualification still fails, the unchanged failure-only job records the six-case
path comparison. No successful Windows qualification is claimed here.
