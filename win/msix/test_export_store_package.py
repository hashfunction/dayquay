"""Real Git/stage/ZIP export with synthetic service and installed-GUI receipts.

These fixtures exercise release boundaries; only Windows can qualify the app.
"""
# Copyright 2026 Trieflow LLC. MIT.
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
import zipfile

import export_store_package as gate
import msix_qualification as msix
import source_publication as publication
import test_msix_qualification as fixtures
from test_store_workflow_evidence import workflow_fixture


class StoreExportTests(unittest.TestCase):
    def setUp(self):
        self.f = f = fixtures.QualificationTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        destination = f.source / 'dist/Jotmorrow'
        destination.parent.mkdir()
        shutil.move(str(f.release), destination)
        f.release = destination
        f.inventory = f.evidence / 'package-inventory.json'
        f.startup = f.evidence / 'windows-startup.json'
        f.artwork = f.source / 'rednotebook/images/jotmorrow-icon/jotmorrow-256.png'
        helper = Path(__file__).with_name('installed_workflow_qualification.py')
        shutil.copyfile(helper, f.source / 'win/msix' / helper.name)
        self.helper_hash = publication.digest(helper.read_bytes())['sha256']
        (f.source / '.gitignore').write_text('/dist/\n/build-evidence/\n*.pyc\n')
        f.refresh_evidence()
        preliminary = json.loads(f.inventory.read_bytes())
        native = preliminary['buildProvenance']['nativeInputs']
        files = preliminary['files']
        self.manifest = json.dumps(dict(archives=[{'fixture': True}], metadata=[])).encode()
        self.closure = dict(
            schema_version=1, source_release=publication.RELEASE_URL,
            source_archive_inputs=1, source_archive_members=2,
            source_manifest=dict(name='source-manifest.json', **publication.digest(self.manifest)),
            source_archive=dict(name='fixture-native-sources.tar', **publication.digest(b'source archive fixture')),
            native_archives=native['archives'], installed_native_versions=native['installedVersions'],
            vendor_payload={p: d for p, d in files.items() if p.endswith(('.dll', '.pyd'))},
            original_notice_payload={p: d for p, d in files.items() if '/notices/' in p},
            notice_supplement_index=preliminary['sourceInputs']['win/notice-supplement/index.json'],
            audit_checks={k: True for k in ('public_release_asset_digests_match', 'source_archive_and_all_members_verified',
                'all_native_archives_unchanged', 'all_native_versions_unchanged', 'all_mapped_vendor_payload_unchanged',
                'all_original_notices_match', 'all_source_inputs_match')})
        self.closure['current_application'] = dict(name='Jotmorrow', version='1.0.1', msix_version='1.0.1.0',
            source_page='https://jotmorrow.trieflow.com/source',
            source_inputs={p: d for p, d in preliminary['sourceInputs'].items() if not p.startswith('win/notice-supplement/')})
        self.write('win/msix/native-source-publication.json', self.closure)
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Qualification fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'Source boundary fixture')
        f.commit = self.git('rev-parse', 'HEAD')
        self.tree = self.git('show', '-s', '--format=%T', 'HEAD')
        f.refresh_evidence()
        self.native = json.loads(f.startup.read_bytes())
        self.native.update(workflow_run_id='12345', workflow_run_attempt='1')
        self.write('build-evidence/windows-startup.json', self.native)
        stage = f.root / 'store-stage'
        self.record = msix.stage_release(f.release, f.artwork, stage, f.commit,
                                        f.inventory, f.startup, f.source, 'store')
        self.package = f.root / gate.PACKAGE_NAME
        with zipfile.ZipFile(self.package, 'w') as archive:
            for relative in self.record['payload']: archive.write(stage / relative, relative)
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('AppxBlockMap.xml', '<BlockMap/>')
        self.record['containerVerification'] = msix.verify_msix(self.package, self.record['payload'], 'store')
        self.record['unpackedVerification'] = msix.verify_unpacked(stage, self.record['payload'], 'store')
        self.write('build-evidence/msix-store-package-record.json', self.record)
        title = self.native['window_title']
        self.workflow, self.installed = workflow_fixture(title, self.helper_hash)
        self.workflow.update(source_commit=f.commit, workflow_run_id='12345', workflow_run_attempt='1')
        self.installed.update(installed_consumer_workflow=copy.deepcopy(self.workflow))
        self.installed.update(source_commit=f.commit, workflow_run_id='12345', workflow_run_attempt='1',
            identity=msix.STORE_IDENTITY, identity_mode='store', qualification_identity_only=False, store_identity_used=True,
            primary_error=None, certificate_private_key_exported=False,
            executable_sha256=self.native['executable_sha256'],
            unsigned_package_sha256=self.record['containerVerification']['package']['sha256'])
        for key in ('add_appx_completed', 'registration_ownership_established', 'unsigned_package_unchanged',
                'process_identity_ownership_established', 'process_shutdown_verified', 'clean_close_verified',
                'uninstall_verified', 'workflow_profile_removed', 'installation_qualification_passed',
                'journal_backup_restore_workflow_tested'):
            self.installed[key] = True
        for key in ('package_full_name', 'owned_package_full_name', 'activated_process_package_full_name'):
            self.installed[key] = gate.PACKAGE_FULL_NAME
        for key in ('preflight_package_full_names', 'residual_package_full_names', 'cleanup_errors', 'evidence_errors'):
            self.installed[key] = []
        self.window = dict(self.installed['window'], title=title, expected_title=title, visible=True,
                           screenshot_captured=True, screenshot_error=None,
                           screenshot_sha256=publication.digest(b'synthetic screenshot bytes')['sha256'])
        self.installed['window'] = self.window
        self.modules = [dict(origin='package', relative_path=p, sha256=self.record['payload'][p]['sha256'])
                        for p in self.record['runtime'].values()]
        self.installed['loaded_module_count'] = len(self.modules)
        self.prefix = 'build-evidence/msix-store-install/'
        self.write(self.prefix + 'qualification-window.png', b'synthetic screenshot bytes')
        self.persist()
        self.remote_release = dict(id=123, draft=False, tag_name=publication.RELEASE_TAG,
            assets=[dict(name=a['name'], size=a['bytes'], digest='sha256:' + a['sha256'],
                         browser_download_url=publication.DOWNLOAD_URL + a['name'])
                    for a in (self.closure['source_manifest'], self.closure['source_archive'])])
        self.remote_commit = dict(sha=f.commit, commit=dict(tree=dict(sha=self.tree)))
        self.output = f.evidence / 'store-export'

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.f.source), *args],
                                capture_output=True, text=True)
        if result.returncode:
            self.fail(f'Git fixture command {args!r} failed: {result.stderr}')
        return result.stdout.strip()

    def write(self, relative, data):
        target = self.f.source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode())

    def persist(self):
        for name, data in [('installation-qualification.json', self.installed), ('installed-consumer-workflow.json', self.workflow),
                           ('loaded-modules.json', self.modules), ('window-observation.json', self.window)]:
            self.write(self.prefix + name, data)

    def fetcher(self, url):
        if url == publication.MANIFEST_URL: return self.manifest
        if '/releases/tags/' in url: return json.dumps(self.remote_release).encode()
        if '/commits/' in url: return json.dumps(self.remote_commit).encode()
        self.fail('Unexpected service request: ' + url)

    def export(self, **kwargs):
        args = dict(package=self.package, source=self.f.source, output=self.output, commit=self.f.commit,
                    reviewed=self.f.commit, run_id='12345', attempt='1', fetcher=self.fetcher)
        args.update(kwargs)
        return gate.export_store_package(**args)

    def test_export_retains_only_exact_unsigned_bytes_and_last_written_receipt(self):
        result = self.export()
        self.assertEqual(set(p.name for p in self.output.iterdir()), {gate.PACKAGE_NAME, 'release-ready.json'})
        self.assertEqual((self.output / gate.PACKAGE_NAME).read_bytes(), self.package.read_bytes())
        self.assertEqual(json.loads((self.output / 'release-ready.json').read_bytes()), result)
        self.assertTrue(result['unsigned_store_package_ready'])
        self.assertFalse(result['submitted'])
        self.assertEqual(result['source_tree'], self.tree)
        self.assertEqual(result['evidence']['win/msix/installed_workflow_qualification.py']['sha256'], self.helper_hash)

    def test_review_source_and_run_substitution_refused_before_output(self):
        for kwargs in (dict(reviewed='0' * 40), dict(commit='0' * 40), dict(run_id='12346'), dict(attempt='2')):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.export(**kwargs)
            self.assertFalse(self.output.exists())
        (self.f.source / 'foreign.txt').write_text('uncommitted')
        with self.assertRaisesRegex(ValueError, 'unchanged committed'): self.export()
        self.assertEqual((self.f.source / 'foreign.txt').read_text(), 'uncommitted')

    def test_installed_proof_failures_cannot_export(self):
        original = copy.deepcopy(self.installed)
        mutations = dict(clean_close_verified=False, uninstall_verified=False, workflow_profile_removed=False,
                         process_identity_ownership_established=False, certificate_private_key_exported=True,
                         cleanup_errors=['unclean'], evidence_errors=['unproved'], residual_package_full_names=['foreign'],
                         activated_process_package_full_name='foreign', unsigned_package_sha256='0' * 64,
                         executable_sha256='0' * 64, journal_backup_restore_workflow_tested=False)
        for key, value in mutations.items():
            with self.subTest(key=key):
                self.installed = copy.deepcopy(original); self.installed[key] = value; self.persist()
                with self.assertRaises(ValueError): self.export()
                self.assertFalse(self.output.exists())

    def test_module_window_workflow_and_unsigned_container_changes_refused(self):
        original_modules, original_window, original_workflow = map(copy.deepcopy, (self.modules, self.window, self.workflow))
        for mutation in ('module-bytes', 'missing-runtime', 'duplicate-runtime', 'unknown-origin', 'window-bytes', 'window-owner', 'workflow-helper'):
            with self.subTest(mutation=mutation):
                self.modules, self.window, self.workflow = map(copy.deepcopy, (original_modules, original_window, original_workflow))
                if mutation == 'module-bytes': self.modules[0]['sha256'] = '0' * 64
                if mutation == 'missing-runtime': self.modules.pop()
                if mutation == 'duplicate-runtime': self.modules.append(copy.deepcopy(self.modules[0]))
                if mutation == 'unknown-origin': self.modules.append(dict(origin='foreign', relative_path=None, sha256='0' * 64))
                if mutation == 'window-bytes': self.window['screenshot_sha256'] = '0' * 64
                if mutation == 'window-owner': self.window['main_window_handle'] = 99
                if mutation == 'workflow-helper': self.workflow['helper_sha256'] = '0' * 64
                self.installed.update(window=self.window, loaded_module_count=len(self.modules), installed_consumer_workflow=copy.deepcopy(self.workflow))
                self.persist()
                with self.assertRaises(ValueError): self.export()
                self.assertFalse(self.output.exists())

    def test_public_source_asset_and_commit_must_match_reviewed_bytes(self):
        release, commit = copy.deepcopy(self.remote_release), copy.deepcopy(self.remote_commit)
        for mutation in ('draft', 'asset-hash', 'asset-url', 'asset-duplicate', 'commit', 'tree'):
            with self.subTest(mutation=mutation):
                self.remote_release, self.remote_commit = copy.deepcopy(release), copy.deepcopy(commit)
                if mutation == 'draft': self.remote_release['draft'] = True
                if mutation == 'asset-hash': self.remote_release['assets'][0]['digest'] = 'sha256:' + '0' * 64
                if mutation == 'asset-url': self.remote_release['assets'][0]['browser_download_url'] = 'https://foreign.invalid/source'
                if mutation == 'asset-duplicate': self.remote_release['assets'].append(copy.deepcopy(self.remote_release['assets'][0]))
                if mutation == 'commit': self.remote_commit['sha'] = '0' * 40
                if mutation == 'tree': self.remote_commit['commit']['tree']['sha'] = '0' * 40
                with self.assertRaises(ValueError): self.export()
                self.assertFalse(self.output.exists())

    def test_unsigned_package_replacement_and_existing_output_preserved(self):
        with zipfile.ZipFile(self.package, 'a') as archive: archive.writestr('AppxSignature.p7x', b'not unsigned')
        changed = self.package.read_bytes()
        with self.assertRaises(ValueError): self.export()
        self.assertEqual(self.package.read_bytes(), changed)
        self.output.mkdir(); foreign = self.output / 'foreign.txt'; foreign.write_bytes(b'protected')
        with self.assertRaises(ValueError): self.export()
        self.assertEqual(foreign.read_bytes(), b'protected')

    def test_late_evidence_change_removes_only_unchanged_owned_output(self):
        original = gate.shutil.copyfileobj
        def change_after_copy(*args, **kwargs):
            original(*args, **kwargs)
            if Path(args[1].name) == self.output / gate.PACKAGE_NAME:
                self.write(self.prefix + 'loaded-modules.json', [])
        with patch.object(gate.shutil, 'copyfileobj', change_after_copy), self.assertRaisesRegex(ValueError, 'evidence changed'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_cleanup_refuses_foreign_or_changed_output_after_late_failure(self):
        original = gate.shutil.copyfileobj
        def add_foreign_after_copy(*args, **kwargs):
            original(*args, **kwargs)
            if Path(args[1].name) == self.output / gate.PACKAGE_NAME:
                (self.output / 'foreign.txt').write_bytes(b'protected')
                self.write(self.prefix + 'loaded-modules.json', [])
        with patch.object(gate.shutil, 'copyfileobj', add_foreign_after_copy), self.assertRaisesRegex(ValueError, 'preserved'):
            self.export()
        self.assertEqual((self.output / 'foreign.txt').read_bytes(), b'protected')
        self.assertFalse((self.output / 'release-ready.json').exists())
        identity = (self.output.stat().st_dev, self.output.stat().st_ino)
        with self.assertRaisesRegex(ValueError, 'Changed export bytes'):
            gate.remove_owned_export(self.output, identity, {'foreign.txt': publication.digest(b'changed'),
                gate.PACKAGE_NAME: msix.file_record(self.package)})
        self.assertEqual((self.output / 'foreign.txt').read_bytes(), b'protected')


if __name__ == '__main__':
    unittest.main()
