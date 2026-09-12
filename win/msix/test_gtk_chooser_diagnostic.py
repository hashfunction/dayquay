"""Boundaries for the standalone, non-qualifying chooser diagnostic."""

from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import gtk_chooser_diagnostic as diagnostic


class ChooserDiagnosticTests(unittest.TestCase):
    def test_removes_only_exact_owned_empty_probe_tree(self):
        root, token = diagnostic.create_probe_tree()
        self.assertTrue((root / "Jotmorrow" / "ReopenProbe").is_dir())
        diagnostic.remove_probe_tree(root, token)
        self.assertFalse(root.exists())

    def test_changed_marker_preserves_tree(self):
        root, token = diagnostic.create_probe_tree()
        marker = root / diagnostic.MARKER
        try:
            marker.write_text("different owner", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "ownership"):
                diagnostic.remove_probe_tree(root, token)
            self.assertTrue(root.exists())
        finally:
            marker.write_text(token, encoding="ascii")
            diagnostic.remove_probe_tree(root, token)

    def test_unexpected_file_preserved_before_any_removal(self):
        root, token = diagnostic.create_probe_tree()
        extra = root / "Jotmorrow" / "ReopenProbe" / "unowned.txt"
        try:
            extra.write_text("preserve", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                diagnostic.remove_probe_tree(root, token)
            self.assertEqual(extra.read_text(), "preserve")
            self.assertTrue((root / diagnostic.MARKER).is_file())
        finally:
            extra.unlink()
            diagnostic.remove_probe_tree(root, token)

    def test_link_substitution_preserves_target(self):
        root, token = diagnostic.create_probe_tree()
        probe = root / "Jotmorrow" / "ReopenProbe"
        with tempfile.TemporaryDirectory() as other:
            probe.rmdir()
            try:
                try:
                    probe.symlink_to(other, target_is_directory=True)
                except OSError:
                    # Windows runners may lack symlink privilege. Exercise the
                    # same fail-closed branch with a reparse-point observation.
                    probe.mkdir()
                    original = diagnostic._is_link_or_reparse
                    with mock.patch.object(
                        diagnostic, "_is_link_or_reparse",
                        side_effect=lambda p: p == probe or original(p),
                    ):
                        with self.assertRaisesRegex(ValueError, "link|reparse"):
                            diagnostic.remove_probe_tree(root, token)
                    return
                with self.assertRaisesRegex(ValueError, "link|reparse"):
                    diagnostic.remove_probe_tree(root, token)
                self.assertTrue(Path(other).is_dir())
            finally:
                if probe.is_symlink():
                    probe.unlink()
                probe.mkdir(exist_ok=True)
                diagnostic.remove_probe_tree(root, token)

    def test_builder_input_preserves_actual_chooser_only(self):
        glade = Path(__file__).resolve().parents[2] / "rednotebook/files/main_window.glade"
        actual = ET.parse(glade).getroot().find("object[@id='dir_chooser']")
        selected = ET.fromstring(diagnostic.chooser_xml(glade))
        self.assertEqual(len(selected.findall("object")), 1)
        self.assertEqual(ET.tostring(selected.find("object")), ET.tostring(actual))
        self.assertEqual(
            selected.find("requires").attrib, {"lib": "gtk+", "version": "3.10"}
        )
        self.assertNotIn("GtkSourceView", diagnostic.chooser_xml(glade))

    def test_save_probe_preserves_actual_backup_dialog_and_response(self):
        glade = Path(__file__).resolve().parents[2] / "rednotebook/files/main_window.glade"
        actual = ET.parse(glade).getroot().find("object[@id='backup_dialog']")
        selected = ET.fromstring(diagnostic.chooser_xml(glade, "backup_dialog"))
        self.assertEqual(len(selected.findall("object")), 1)
        self.assertEqual(ET.tostring(selected.find("object")), ET.tostring(actual))
        self.assertEqual(selected.find("object/property[@name='action']").text, "save")
        with self.assertRaisesRegex(ValueError, "chooser"):
            diagnostic.chooser_xml(glade, "main_window")

    def test_native_and_direct_cases_have_distinct_actions(self):
        for action, expected in (
            ("enter", [mock.call._foreground(17, "chooser"), mock.call.press("ENTER")]),
            ("alt_o", [mock.call._foreground(17, "chooser"), mock.call.chord("ALT", "O")]),
            ("activate_default", [mock.call._foreground(17, "chooser")]),
        ):
            with self.subTest(action=action):
                native = mock.Mock()
                direct = mock.Mock(return_value=True)
                diagnostic.dispatch_action(native, 17, "chooser", action, direct)
                self.assertEqual(native.mock_calls, expected)
                self.assertEqual(direct.call_count, int(action == "activate_default"))

    def test_path_comparison_keeps_both_spellings_of_one_local_target(self):
        expected_native = "D:\\a\\_temp\\Jotmorrow\\Café, notes"
        expected_forward = "D:/a/_temp/Jotmorrow/Café, notes"
        for supplied in (expected_native, expected_forward):
            self.assertEqual(diagnostic.chooser_target(supplied, "native"), expected_native)
            self.assertEqual(diagnostic.chooser_target(supplied, "forward_slash"), expected_forward)
        with self.assertRaisesRegex(ValueError, "path spelling"):
            diagnostic.chooser_target(expected_native, "other")

    def test_native_path_case_reuses_installed_input_conversion(self):
        with mock.patch.object(diagnostic, "_windows_chooser_path", return_value="converted") as convert:
            self.assertEqual(diagnostic.chooser_target("C:/Jotmorrow/data", "native"), "converted")
        convert.assert_called_once_with("C:/Jotmorrow/data")

    def test_foreign_foreground_refusal_stops_every_action(self):
        for action in diagnostic.ACTIONS:
            native = mock.Mock()
            native._foreground.side_effect = ValueError("ownership changed")
            direct = mock.Mock()
            with self.assertRaisesRegex(ValueError, "ownership"):
                diagnostic.dispatch_action(native, 17, "chooser", action, direct)
            native.press.assert_not_called()
            native.chord.assert_not_called()
            direct.assert_not_called()

    def test_unknown_action_does_not_target_any_window(self):
        native, direct = mock.Mock(), mock.Mock()
        with self.assertRaises(ValueError):
            diagnostic.dispatch_action(native, 17, "chooser", "other", direct)
        self.assertFalse(native.mock_calls)
        direct.assert_not_called()


if __name__ == "__main__":
    unittest.main()
