"""Real file/ZIP/XML fixtures for packaging boundaries; no native/GUI claims.
Copyright 2026 Trieflow LLC. MIT, derived in part from PixelQuay's MIT tests.
"""

import ast
import copy
import datetime
import locale
import types
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from junction_fixture import WindowsJunctionFixture

try:
    import msix_qualification as msix
except ImportError:
    msix = None


def digest(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


class QualificationTests(WindowsJunctionFixture, unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(msix, "DayQuay MSIX qualification is not implemented")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.release = self.root / "release"
        self.source = self.root / "source"
        real_source = Path(__file__).resolve().parents[2]
        self.artwork = real_source / "rednotebook/images/dayquay-icon/dayquay-256.png"
        self.commit = "a" * 40
        # Use the actual checked-in title, build definition, notices and artwork.
        for relative in (
            "LICENSE",
            "debian",
            "LICENSES",
            "win",
            "rednotebook/info.py",
            "rednotebook/product.py",
            "rednotebook/journal.py",
            "rednotebook/configuration.py",
            "rednotebook/util/dates.py",
            "rednotebook/external/elibintl.py",
            "win/msix/window_title_contract.py",
            "rednotebook/gui/main_window.py",
            "rednotebook/images/dayquay-icon",
            "rednotebook/files",
        ):
            original = real_source / relative
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if original.is_dir():
                shutil.copytree(
                    original, target, ignore=shutil.ignore_patterns("__pycache__", "msix")
                )
            else:
                shutil.copyfile(original, target)
        self.release.mkdir()
        files = {
            "DayQuay.exe": b"PyInstaller embedded bootloader output",
            "_internal/libpython3.14.dll": b"MSYS2 Python runtime",
            "_internal/libgtk-3-0.dll": b"GTK3 runtime",
            "_internal/libgtksourceview-4-0.dll": b"GtkSource4 runtime",
            "_internal/bin/libenchant-2-2.dll": b"Enchant runtime",
            "_internal/gi/_gi.cp314-mingw_x86_64_ucrt_gnu.pyd": b"PyGObject native binding",
            "_internal/lib/enchant-2/enchant_hunspell.dll": b"Hunspell provider",
            "_internal/gi_typelibs/Gtk-3.0.typelib": b"GTK typelib",
            "_internal/gi_typelibs/GtkSource-4.typelib": b"GtkSource typelib",
            "_internal/share/hunspell/en_US.aff": b"dictionary affix",
            "_internal/share/hunspell/en_US.dic": b"dictionary words",
            "_internal/help/index.html": b"help resource",
        }
        for relative, data in files.items():
            path = self.release / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for original, target in [
            ("LICENSE", "LICENSE"),
            ("debian/copyright", "copyright"),
            ("win/THIRD-PARTY-NOTICES.txt", "THIRD-PARTY-NOTICES.txt"),
            ("win/windows-dependencies.json", "windows-dependencies.json"),
            ("LICENSES", "LICENSES"),
            ("rednotebook/images/dayquay-icon", "images/dayquay-icon"),
            ("rednotebook/files", "files"),
            ("win/notice-supplement", "notices/supplement"),
        ]:
            source = self.source / original
            dest = self.release / "_internal" / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, dest)
            else:
                shutil.copyfile(source, dest)
        self.evidence = self.source / "build-evidence"
        self.evidence.mkdir()
        cache = self.evidence / "package-cache"
        cache.mkdir()
        declaration = json.loads((self.source / "win/windows-dependencies.json").read_text())
        versions, hashes = [], []
        for package in declaration["packages"]:
            if not package["name"].startswith("mingw-"):
                continue
            archive = package["archive"].rsplit("/", 1)[1]
            data = (package["name"] + " native archive fixture").encode()
            (cache / archive).write_bytes(data)
            package["sha256"] = digest(data)["sha256"]
            versions.append(package["name"] + " " + package["version"])
            hashes.append(package["sha256"] + "  build-evidence/package-cache/" + archive)
        data = json.dumps(declaration).encode()
        (self.source / "win/windows-dependencies.json").write_bytes(data)
        (self.release / "_internal/windows-dependencies.json").write_bytes(data)
        for name in ("native-installed-versions.txt", "native-downloaded-versions.txt"):
            (self.evidence / name).write_text("\n".join(sorted(versions)) + "\n")
        (self.evidence / "msys2-cache-sha256.txt").write_text("\n".join(hashes) + "\n")
        (self.evidence / "msys2-package-metadata.txt").write_text("Actual pacman metadata fixture")
        (self.evidence / "msys2-package-files.txt").write_text(
            "Actual pacman file inventory fixture"
        )
        (self.evidence / "native-runtime.json").write_text(
            json.dumps(
                dict(
                    status="native_runtime_qualified_not_packaged",
                    gtk=[3, 24, 52],
                    spellcheck="en_US correct and incorrect words verified",
                    python="3.14.7",
                )
            )
        )
        notice = self.release / "_internal/notices/native/python/LICENSE"
        notice.parent.mkdir(parents=True, exist_ok=True)
        notice.write_bytes(b"Collected installed Python notice fixture")
        (self.evidence / "packaging-python.json").write_text(
            json.dumps(dict(path=sys.executable, **digest(Path(sys.executable).read_bytes())))
        )
        self.notice_path = self.evidence / "native-notices.json"
        self.notices = {
            "files": msix.inventory_tree(self.release / "_internal/notices"),
            "unresolved": ["Corresponding source and complete native license audit required"],
            "inventoryIsLicenseClearance": False,
        }
        self.notice_path.write_text(json.dumps(self.notices))
        self.inventory = self.root / "inventory.json"
        self.startup = self.root / "startup.json"
        self.refresh_evidence()

    def test_native_archive_hashes_accept_sha256sum_binary_markers(self):
        path = self.evidence / "msys2-cache-sha256.txt"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(
            "\n".join(line[:65] + "*" + line[66:] for line in lines) + "\n",
            encoding="utf-8",
        )
        record = msix.native_build_inputs(self.source)
        self.assertEqual(record["archives"], msix.inventory_tree(self.evidence / "package-cache"))

    def refresh_evidence(self):
        record = msix.create_input_inventory(self.release, self.source, self.commit)
        self.inventory.write_text(json.dumps(record))
        self.startup.write_text(
            json.dumps(
                dict(
                    source_commit=self.commit,
                    windows_native_startup=True,
                    window_title=msix.create_title_contract(self.source)["expectedTitle"],
                    window_title_contract=msix.create_title_contract(self.source),
                    executable_sha256=record["files"]["DayQuay.exe"]["sha256"],
                    package_inventory_sha256=digest(self.inventory.read_bytes())["sha256"],
                    interactive_backup_restore_verified=False,
                    native_source_clearance=False,
                    msix_built=False,
                    submitted=False,
                )
            )
        )

    def stage(self):
        return msix.stage_release(
            self.release,
            self.artwork,
            self.root / "stage",
            self.commit,
            self.inventory,
            self.startup,
            self.source,
        )

    def test_complete_stage_source_notices_and_receipt_binding(self):
        record = self.stage()
        self.assertEqual(record["releaseInput"], msix.inventory_tree(self.release))
        self.assertEqual(record["payload"], msix.inventory_tree(self.root / "stage"))
        self.assertEqual(record["sourceCommit"], self.commit)
        self.assertEqual(
            record["startupReceipt"]["sha256"], digest(self.startup.read_bytes())["sha256"]
        )
        self.assertEqual(record["runtime"]["executable"], "DayQuay.exe")
        self.assertTrue(record["unresolvedNotices"])
        self.assertFalse(record["licenseClearanceClaimed"])
        self.assertFalse(record["publicRelease"])
        self.assertIn("build output", record["buildProvenance"]["bootloader"])
        for name, size in [
            ("StoreLogo.png", 50),
            ("Square44x44Logo.png", 44),
            ("Square150x150Logo.png", 150),
        ]:
            self.assertEqual(
                msix.png_dimensions((self.root / "stage/Assets" / name).read_bytes()), (size, size)
            )

    def test_flat_enchant_broker_layout_is_rejected(self):
        stale = self.release / "_internal/libenchant-2-2.dll"
        stale.write_bytes(b"old layout that gives PyEnchant the wrong prefix")
        with self.assertRaisesRegex(ValueError, "provider-prefix"):
            self.refresh_evidence()

    def test_original_notice_copy_is_required_even_if_notice_receipt_is_refreshed(self):
        target = self.release / "_internal/notices/supplement/upstream/libyaml/License"
        original = target.read_bytes()
        for mutation in ("missing", "corrupt"):
            with self.subTest(mutation=mutation):
                target.unlink() if mutation == "missing" else target.write_bytes(b"changed")
                self.notices["files"] = msix.inventory_tree(self.release / "_internal/notices")
                self.notice_path.write_text(json.dumps(self.notices), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Original source notice"):
                    self.refresh_evidence()
                target.write_bytes(original)

    def test_inventory_or_stage_tampering_extra_and_omitted_files_rejected(self):
        for mode in ("changed", "extra", "missing"):
            with self.subTest(mode=mode):
                path = self.release / "_internal/help/index.html"
                original = path.read_bytes()
                extra = self.release / "unexpected.dll"
                if mode == "changed":
                    path.write_bytes(b"altered")
                if mode == "extra":
                    extra.write_bytes(b"undeclared")
                if mode == "missing":
                    path.unlink()
                with self.assertRaises(ValueError):
                    self.stage()
                path.write_bytes(original)
                extra.unlink(missing_ok=True)

    def test_changed_runtime_notices_or_original_images_rejected_even_with_fresh_inventory(self):
        for relative in (
            "_internal/LICENSE",
            "_internal/THIRD-PARTY-NOTICES.txt",
            "_internal/images/dayquay-icon/dayquay-32.png",
        ):
            path = self.release / relative
            original = path.read_bytes()
            path.write_bytes(b"changed")
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                self.refresh_evidence()
            path.write_bytes(original)
        for relative in (
            "_internal/libpython3.14.dll",
            "_internal/gi/_gi.cp314-mingw_x86_64_ucrt_gnu.pyd",
            "_internal/libgtk-3-0.dll",
            "_internal/libgtksourceview-4-0.dll",
            "_internal/notices/native/python/LICENSE",
        ):
            path = self.release / relative
            original = path.read_bytes()
            path.unlink()
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                self.refresh_evidence()
            path.write_bytes(original)

    def test_ambiguous_pygobject_runtime_rejected(self):
        (self.release / "_internal/gi/_gi.other.pyd").write_bytes(b"ambiguous binding")
        with self.assertRaises(ValueError):
            self.refresh_evidence()

    def test_source_copied_notice_changes_rejected_before_receipts_can_be_refreshed(self):
        for relative in ("_internal/copyright", "_internal/LICENSES/GPL-3.0.txt"):
            path = self.release / relative
            original = path.read_bytes()
            with self.subTest(relative=relative):
                path.write_bytes(b"replaced third-party license text")
                with self.assertRaisesRegex(ValueError, "Original source"):
                    self.refresh_evidence()
            path.write_bytes(original)

    def test_missing_native_notice_cannot_be_hidden_by_new_inventory(self):
        (self.release / "_internal/notices/native/python/LICENSE").unlink()
        with self.assertRaises(ValueError):
            self.refresh_evidence()

    def test_native_version_and_cached_archive_mismatch_rejected(self):
        path = self.evidence / "native-downloaded-versions.txt"
        original = path.read_bytes()
        path.write_bytes(b"wrong version")
        with self.assertRaises(ValueError):
            self.refresh_evidence()
        path.write_bytes(original)
        archive = next((self.evidence / "package-cache").glob("*.zst"))
        archive.write_bytes(b"changed cached archive")
        with self.assertRaises(ValueError):
            self.refresh_evidence()

    def test_changed_build_metadata_requires_a_new_bound_startup(self):
        (self.evidence / "msys2-package-metadata.txt").write_bytes(b"different input provenance")
        with self.assertRaises(ValueError):
            self.stage()

    def test_coherent_foreign_source_receipt_and_inventory_rejected(self):
        inventory = json.loads(self.inventory.read_text())
        inventory["sourceCommit"] = "b" * 40
        self.inventory.write_text(json.dumps(inventory))
        receipt = json.loads(self.startup.read_text())
        receipt["source_commit"] = "b" * 40
        receipt["package_inventory_sha256"] = digest(self.inventory.read_bytes())["sha256"]
        self.startup.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError):
            self.stage()

    def test_changed_source_metadata_rejected(self):
        (self.source / "win/pyenchant-source-lock.txt").write_bytes(
            b"resolved different dependencies"
        )
        with self.assertRaises(ValueError):
            self.stage()

    def test_actual_source_title_and_native_set_title_match_observer(self):
        actual = Path(__file__).resolve().parents[2]
        self.assertIn("rednotebook/info.py", msix.source_inputs(actual))
        for relative, before, after in [
            ("rednotebook/info.py", 'program_name = "DayQuay"', 'program_name = "Drift"'),
            (
                "rednotebook/gui/main_window.py",
                "set_title(info.program_name)",
                'set_title("Drift")',
            ),
            ("rednotebook/journal.py", '" - ".join(parts)', '" - error ".join(parts)'),
            (
                "rednotebook/configuration.py",
                '"exportDateFormat": "%A, %x"',
                '"exportDateFormat": "error"',
            ),
        ]:
            path = self.source / relative
            original = path.read_text()
            self.assertIn(before, original)
            path.write_text(original.replace(before, after))
            with self.assertRaises(ValueError):
                self.refresh_evidence()
            path.write_text(original)

    def test_actual_journal_stable_date_title_is_accepted(self):
        # Execute the actual production method and date formatter without importing GTK.
        # This reproduces the later title mutation missed by the initial-window test.
        namespace = {"datetime": datetime}
        date_tree = ast.parse((self.source / "rednotebook/util/dates.py").read_text())
        formatter = next(
            n for n in date_tree.body if isinstance(n, ast.FunctionDef) and n.name == "format_date"
        )
        exec(
            compile(ast.Module(body=[formatter], type_ignores=[]), "actual dates.py", "exec"),
            namespace,
        )
        config_tree = ast.parse((self.source / "rednotebook/configuration.py").read_text())
        defaults = next(
            n.value
            for n in ast.walk(config_tree)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "defaults" for t in n.targets)
        )
        defaults = ast.literal_eval(defaults)
        journal_tree = ast.parse((self.source / "rednotebook/journal.py").read_text())
        method = next(
            n
            for n in ast.walk(journal_tree)
            if isinstance(n, ast.FunctionDef) and n.name == "set_frame_title"
        )
        titles = []
        namespace.update(
            info=types.SimpleNamespace(program_name="DayQuay"),
            dates=types.SimpleNamespace(format_date=namespace["format_date"]),
        )
        exec(
            compile(ast.Module(body=[method], type_ignores=[]), "actual Journal", "exec"), namespace
        )
        locale.setlocale(locale.LC_ALL, "")
        today = datetime.date.today()
        journal = types.SimpleNamespace(
            title="data",
            date=today,
            config=types.SimpleNamespace(read=defaults.__getitem__),
            frame=types.SimpleNamespace(main_frame=types.SimpleNamespace(set_title=titles.append)),
        )
        namespace["set_frame_title"](journal)
        title = titles.pop()
        self.assertNotEqual(title, "DayQuay")
        receipt = json.loads(self.startup.read_text())
        receipt.update(
            window_title=title,
            window_title_contract=dict(
                schemaVersion=1,
                localDate=today.isoformat(),
                locale=locale.setlocale(locale.LC_TIME),
                expectedTitle=title,
            ),
        )
        self.startup.write_text(json.dumps(receipt))
        self.stage()

    def test_changed_or_unproven_startup_receipt_rejected(self):
        original = json.loads(self.startup.read_text())
        for key, value in [
            ("source_commit", "b" * 40),
            ("executable_sha256", "f" * 64),
            ("package_inventory_sha256", "f" * 64),
            ("windows_native_startup", False),
            ("window_title", "DayQuay error"),
            ("window_title", "DayQuay"),
            ("window_title", original["window_title"] + " "),
            ("window_title", original["window_title"] + " - error"),
            ("window_title_contract", None),
        ]:
            receipt = copy.deepcopy(original)
            receipt[key] = value
            self.startup.write_text(json.dumps(receipt))
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.stage()

    def test_coherently_changed_title_contract_is_rejected(self):
        original = json.loads(self.startup.read_text())
        for key, value in [
            ("expectedTitle", "DayQuay"),
            ("expectedTitle", "DayQuay - error"),
            ("localDate", "2000-01-01"),
            ("locale", "unobserved-locale"),
            ("schemaVersion", True),
            ("extra", True),
        ]:
            receipt = copy.deepcopy(original)
            receipt["window_title_contract"][key] = value
            receipt["window_title"] = receipt["window_title_contract"]["expectedTitle"]
            self.startup.write_text(json.dumps(receipt))
            with self.subTest(key=key, value=value), self.assertRaisesRegex(
                ValueError, "title contract"
            ):
                self.stage()

    def test_title_contract_cli_uses_source_and_exclusive_publication(self):
        output = self.root / "title-contract.json"
        helper = self.source / "win/msix/window_title_contract.py"
        args = [
            sys.executable,
            str(helper),
            "--source-root",
            str(self.source),
            "--output",
            str(output),
        ]
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_bytes()), msix.create_title_contract(self.source))
        before = output.read_bytes()
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), before)

    def test_stage_and_build_output_never_overwrite_existing_directory(self):
        stage = self.root / "stage"
        stage.mkdir()
        marker = stage / "owner.txt"
        marker.write_text("preserve")
        with self.assertRaises(ValueError):
            self.stage()
        self.assertEqual(marker.read_text(), "preserve")

    def test_junction_command_uses_native_paths_from_msys_spelling(self):
        completed = subprocess.CompletedProcess([], 0, stdout=b"created", stderr=b"")
        with patch("subprocess.run", return_value=completed) as run:
            self.create_windows_junction(
                "D:/a/_temp/msys64/tmp/fixture/release/redirect directory",
                "D:/a/_temp/msys64/tmp/fixture/external directory",
            )
        arguments = run.call_args.args[0]
        self.assertEqual(
            arguments[-2:],
            [
                r"D:\a\_temp\msys64\tmp\fixture\release\redirect directory",
                r"D:\a\_temp\msys64\tmp\fixture\external directory",
            ],
        )
        # Windows subprocess serialization must retain each path as one operand.
        command = subprocess.list2cmdline(arguments)
        self.assertIn('"' + arguments[-2] + '"', command)
        self.assertIn('"' + arguments[-1] + '"', command)

    def test_junction_failure_retains_native_diagnostics(self):
        failed = subprocess.CompletedProcess(
            [], 1, stdout="mklink stdout", stderr="native syntax error"
        )
        with patch("subprocess.run", return_value=failed), self.assertRaisesRegex(
            AssertionError, "native syntax error"
        ):
            self.create_windows_junction("D:/fixture/link", "D:/fixture/target")

    def test_junction_fixture_refuses_cmd_expansion_or_control_characters(self):
        for character in ('"', "%", "!", "&", "|", "^", "<", ">", "\r", "\n"):
            with self.subTest(character=character), patch("subprocess.run") as run:
                with self.assertRaises(AssertionError):
                    self.create_windows_junction("D:/fixture/link" + character, "D:/fixture/target")
                run.assert_not_called()

    def test_directory_link_or_native_junction_is_not_followed(self):
        link = self.release / "redirect directory"
        target = self.root / "external directory"
        target.mkdir()
        if os.name == "nt":
            self.create_windows_junction(link, target)
        else:
            link.symlink_to(target, target_is_directory=True)
        try:
            if os.name == "nt":
                self.assertTrue(link.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
                self.assertEqual(link.lstat().st_reparse_tag, stat.IO_REPARSE_TAG_MOUNT_POINT)
            with self.assertRaisesRegex(ValueError, "reparse"):
                self.stage()
        finally:
            link.rmdir() if os.name == "nt" else link.unlink()

    def package(self):
        record = self.stage()
        path = self.root / "fixture.msix"
        with zipfile.ZipFile(path, "w") as archive:
            for relative in record["payload"]:
                archive.write(self.root / "stage" / relative, relative)
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("AppxBlockMap.xml", "<BlockMap/>")
        return path, record

    def test_exact_container_and_unpacked_payload_match(self):
        package, record = self.package()
        self.assertEqual(
            msix.verify_msix(package, record["payload"])["verifiedPayloadFiles"],
            len(record["payload"]),
        )
        self.assertEqual(
            msix.verify_unpacked(self.root / "stage", record["payload"])["verifiedPayloadFiles"],
            len(record["payload"]),
        )

    def test_installed_inventory_allows_only_signature_metadata_beyond_payload(self):
        record = self.stage()
        stage = self.root / "stage"
        (stage / "AppxSignature.p7x").write_bytes(b"ephemeral signing metadata fixture")
        self.assertEqual(
            msix.verify_installed(stage, record["payload"])["verifiedPayloadFiles"],
            len(record["payload"]),
        )
        (stage / "unexpected-resource.txt").write_bytes(b"unrecorded installed resource")
        with self.assertRaises(ValueError):
            msix.verify_installed(stage, record["payload"])

    def test_install_preflight_rejects_coherently_rehashed_package_record(self):
        package, record = self.package()
        record_path = self.root / "package-record.json"
        record["containerVerification"] = msix.verify_msix(package, record["payload"])
        record["unpackedVerification"] = msix.verify_unpacked(
            self.root / "stage", record["payload"]
        )
        record_path.write_text(json.dumps(record))
        self.assertTrue(
            msix.verify_record_inputs(
                package,
                record_path,
                self.release,
                self.artwork,
                self.commit,
                self.inventory,
                self.startup,
                self.source,
            )
        )
        # An internally consistent hash/record cannot substitute another input revision.
        record["sourceCommit"] = "b" * 40
        record_path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            msix.verify_record_inputs(
                package,
                record_path,
                self.release,
                self.artwork,
                self.commit,
                self.inventory,
                self.startup,
                self.source,
            )
        record["sourceCommit"] = self.commit
        record["runtime"] = {}
        record_path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            msix.verify_record_inputs(
                package,
                record_path,
                self.release,
                self.artwork,
                self.commit,
                self.inventory,
                self.startup,
                self.source,
            )

    def test_unpack_record_is_complete_typed_and_source_bound(self):
        package, record = self.package()
        record["containerVerification"] = msix.verify_msix(package, record["payload"])
        record_path = self.root / "package-record.json"
        for value in (
            None,
            {},
            {"verifiedPayloadFiles": 0},
            {"verifiedPayloadFiles": str(len(record["payload"]))},
            {"verifiedPayloadFiles": float(len(record["payload"]))},
            {"verifiedPayloadFiles": True},
            {"verifiedPayloadFiles": len(record["payload"]) - 1},
            {"verifiedPayloadFiles": len(record["payload"]), "extra": True},
        ):
            changed = copy.deepcopy(record)
            if value is not None:
                changed["unpackedVerification"] = value
            record_path.write_text(json.dumps(changed))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "unpack"):
                msix.verify_record_inputs(
                    package,
                    record_path,
                    self.release,
                    self.artwork,
                    self.commit,
                    self.inventory,
                    self.startup,
                    self.source,
                )

    def test_opc_decodes_once_and_accepts_exact_bytes(self):
        package, record = self.package()
        for encoded, decoded in [
            ("libc%2B%2B.dll", "libc++.dll"),
            ("literal%2520.txt", "literal%20.txt"),
            ("R%C3%A9sum%C3%A9.txt", "Résumé.txt"),
        ]:
            data = b"fixture bytes"
            with zipfile.ZipFile(package, "a") as archive:
                archive.writestr(encoded, data)
            record["payload"][decoded] = digest(data)
        msix.verify_msix(package, record["payload"])

    def test_opc_alias_traversal_bad_utf8_and_special_paths_rejected(self):
        package, record = self.package()
        for name in (
            "%44ayQuay.exe",
            "dayquay.EXE",
            "_internal%2fescape.dll",
            "_internal%5cescape.dll",
            "%2e%2e/escape",
            "/absolute",
            "C:evil",
            "x%FF",
            "x%GG",
            "x%00",
            "CON.txt",
            "name.",
            "empty//name",
        ):
            changed = self.root / "changed.msix"
            shutil.copyfile(package, changed)
            with zipfile.ZipFile(changed, "a") as archive:
                archive.writestr(name, b"extra")
            with self.subTest(name=name), self.assertRaises(ValueError):
                msix.verify_msix(changed, record["payload"])

    def test_zip_link_and_unexpected_empty_directory_rejected(self):
        package, record = self.package()
        for name, mode in [("redirect", 0o120777), ("unreviewed/", 0o40755)]:
            changed = self.root / "changed.msix"
            shutil.copyfile(package, changed)
            info = zipfile.ZipInfo(name)
            info.external_attr = mode << 16
            with zipfile.ZipFile(changed, "a") as archive:
                archive.writestr(info, b"")
            with self.assertRaises(ValueError):
                msix.verify_msix(changed, record["payload"])

    def test_manifest_semantics_independent_of_coherent_hashes(self):
        package, record = self.package()
        for before, after in [
            (b"runFullTrust", b"internetClient"),
            (b"DayQuay.exe", b"other.exe"),
            (b"CN=DayQuay-CI-Qualification", b"CN=foreign"),
        ]:
            data = (self.root / "stage/AppxManifest.xml").read_bytes().replace(before, after)
            with self.assertRaises(ValueError):
                msix.validate_manifest(data)
        root = self.root / "stage"
        (root / "AppxManifest.xml").write_bytes(data)
        record["payload"]["AppxManifest.xml"] = digest(data)
        with self.assertRaises(ValueError):
            msix.verify_unpacked(root, record["payload"])

    def test_exact_sdk_semantic_pack_unpack_and_tool_integrity(self):
        sdk = self.root / "Windows Kits/10/bin/10.0.26100.0/x64"
        sdk.mkdir(parents=True)
        tool = sdk / "makeappx.exe"
        tool.write_bytes(b"fixture tool")
        commands = []

        def runner(command):
            commands.append(command)
            p = Path(command[command.index("/p") + 1])
            d = Path(command[command.index("/d") + 1])
            if command[1] == "pack":
                with zipfile.ZipFile(p, "w") as z:
                    for f in d.rglob("*"):
                        if f.is_file():
                            z.write(f, f.relative_to(d).as_posix())
                    z.writestr("[Content_Types].xml", "<Types/>")
                    z.writestr("AppxBlockMap.xml", "<BlockMap/>")
            else:
                with zipfile.ZipFile(p) as z:
                    z.extractall(d)

        output = self.root / "package-output"
        msix.build_qualification(
            self.release,
            self.artwork,
            self.commit,
            tool,
            "10.0.26100.0",
            output,
            self.inventory,
            self.startup,
            self.source,
            runner,
        )
        self.assertEqual([c[1] for c in commands], ["pack", "unpack"])
        self.assertNotIn("/nv", commands[0])
        self.assertNotIn("/o", commands[0])
        self.assertIn("/v", commands[0])
        record = json.loads((output / "package-record.json").read_text())
        self.assertFalse(record["signed"])
        self.assertFalse(record["installationQualificationPassed"])
        self.assertEqual(record["makeAppx"]["sha256"], digest(tool.read_bytes())["sha256"])
        with self.assertRaises(ValueError):
            msix._tool_record(tool, "10.0.22621.0")

    def test_sdk_tool_change_aborts_without_publishing_output(self):
        sdk = self.root / "Windows Kits/10/bin/10.0.26100.0/x64"
        sdk.mkdir(parents=True)
        tool = sdk / "makeappx.exe"
        tool.write_bytes(b"original SDK tool")

        def changing_tool(command):
            tool.write_bytes(b"changed SDK tool")

        output = self.root / "package-output"
        with self.assertRaisesRegex(ValueError, "MakeAppx changed"):
            msix.build_qualification(
                self.release,
                self.artwork,
                self.commit,
                tool,
                "10.0.26100.0",
                output,
                self.inventory,
                self.startup,
                self.source,
                changing_tool,
            )
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
