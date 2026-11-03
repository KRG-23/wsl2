import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = load('migration')
compare = load('compare')
baseline = load('fetch-baseline')
relocation = load('relocation')


class InventoryTests(unittest.TestCase):
    def test_windows_profile_relocation_handles_json_and_similar_names(self):
        text = 'C:\\Users\\old\\file /mnt/c/Users/old/file C:\\\\Users\\\\old\\\\file /mnt/c/Users/old-user/file'
        updated = relocation.relocate(text, '/mnt/c/Users/old', '/mnt/d/Users/new')
        self.assertEqual(updated, 'D:\\Users\\new\\file /mnt/d/Users/new/file D:\\\\Users\\\\new\\\\file /mnt/c/Users/old-user/file')

    def test_dependencies_and_version_drift_are_separate(self):
        old = {'schema': 1, 'package_inventory_ok': True, 'packages': {'base': '1', 'gone': '1'}}
        new = {'schema': 1, 'package_inventory_ok': True, 'packages': {'base': '2', 'tool': '3'}}
        result = compare.compare(old, new)
        self.assertEqual(result['added_packages'], {'tool': '3'})
        self.assertEqual(result['removed_packages'], {'gone': '1'})
        self.assertEqual(result['changed_versions'], {'base': {'baseline': '1', 'current': '2'}})

    def test_incomplete_inventory_is_rejected(self):
        with self.assertRaises(ValueError):
            compare.compare({'schema': 1}, {'schema': 1})

    def test_dpkg_status_architecture(self):
        status = 'Package: libc6\nStatus: install ok installed\nArchitecture: amd64\nMulti-Arch: same\nVersion: 2.41\n\nPackage: removed\nStatus: deinstall ok config-files\nVersion: 1\n'
        self.assertEqual(baseline.parse_status(status), {'libc6:amd64': '2.41'})


class ArchiveSafetyTests(unittest.TestCase):
    def test_traversal_absolute_and_special_members_rejected(self):
        with tempfile.TemporaryDirectory() as target:
            for name in ['../escape', '/etc/shadow', 'home/../../escape', 'other/file']:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    migration.check_member(tarfile.TarInfo(name), target)
            info = tarfile.TarInfo('home/device')
            info.type = tarfile.CHRTYPE
            with self.assertRaises(ValueError):
                migration.check_member(info, target)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as target:
            info = tarfile.TarInfo('home/escape')
            info.type = tarfile.SYMTYPE
            info.linkname = '/etc'
            with self.assertRaises(tarfile.FilterError):
                migration.check_member(info, target)

    def test_volume_uid_preserved_and_setuid_removed(self):
        with tempfile.TemporaryDirectory() as target:
            info = tarfile.TarInfo('volumes/db/file')
            info.uid, info.gid, info.mode = 999, 998, 0o4755
            safe = migration.check_member(info, target)
            self.assertEqual((safe.uid, safe.gid), (999, 998))
            self.assertFalse(safe.mode & 0o4000)
            directory = tarfile.TarInfo('home/devops/project')
            directory.type, directory.mode = tarfile.DIRTYPE, 0o755
            self.assertEqual(migration.check_member(directory, target).mode, 0o755)

    def test_project_lockfile_kept_but_cache_excluded(self):
        self.assertIsNotNone(migration.backup_filter(tarfile.TarInfo('home/devops/project/poetry.lock')))
        self.assertIsNone(migration.backup_filter(tarfile.TarInfo('home/devops/project/node_modules/a')))

    def test_database_volume_files_are_not_treated_as_caches(self):
        for name in ['volumes/db/cache/file', 'volumes/db/.cache/file', 'volumes/db/artifacts/file', 'volumes/db/file-shm']:
            with self.subTest(name=name):
                self.assertIsNotNone(migration.backup_filter(tarfile.TarInfo(name)))

    def test_remote_editor_settings_retained_and_project_artifacts_retained(self):
        for name in ['home/.vscode-server/data/Machine/settings.json', 'home/devops/project/artifacts/important']:
            self.assertIsNotNone(migration.backup_filter(tarfile.TarInfo(name)))


@unittest.skipUnless(shutil.which('age') and shutil.which('age-keygen'), 'age CLI required')
class EncryptedRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / 'home-source'
        self.home.mkdir()
        (self.home / '.ssh').mkdir()
        (self.home / '.ssh/id_test').write_text('TEST-ONLY private bytes\n')
        (self.home / 'devops/project/.git').mkdir(parents=True)
        (self.home / 'devops/project/local-untracked.txt').write_text('work in progress')
        (self.home / 'devops/project/poetry.lock').write_text('lock')
        (self.home / 'devops/project/node_modules').mkdir()
        (self.home / 'devops/project/node_modules/cache').write_text('discard')
        (self.home / 'devops/project/absolute').symlink_to(self.home / '.ssh/id_test')
        (self.home / 'devops/project/external').symlink_to('/etc/passwd')
        self.identity = self.root / 'identity.txt'
        subprocess.run(['age-keygen', '-o', str(self.identity)], capture_output=True, check=True)
        self.recipient = subprocess.check_output(['age-keygen', '-y', str(self.identity)], text=True).strip()
        self.archive = self.root / 'backup.age'
        self.args = argparse.Namespace(home=self.home, windows_home=None, recipient=self.recipient,
                                       output=self.archive, extra_home=[], acknowledge_quiesced=True,
                                       docker=False, stop_containers=False, system_odbc=False, ignore_bind=[])

    def tearDown(self):
        self.temp.cleanup()

    def test_encrypted_roundtrip_retains_work_and_omits_caches(self):
        migration.backup(self.args)
        self.assertNotIn(b'TEST-ONLY private bytes', self.archive.read_bytes())
        target = self.root / 'restored'
        migration.restore(argparse.Namespace(archive=self.archive, identity=self.identity, into=target))
        self.assertTrue((target / '.verified').is_file())
        self.assertEqual((target / 'home/.ssh/id_test').read_text(), 'TEST-ONLY private bytes\n')
        self.assertTrue((target / 'home/devops/project/local-untracked.txt').is_file())
        self.assertTrue((target / 'home/devops/project/poetry.lock').is_file())
        self.assertFalse((target / 'home/devops/project/node_modules').exists())
        self.assertTrue((target / 'home/devops/project/absolute').resolve().is_relative_to(target))
        manifest = json.loads((target / 'manifest.json').read_text())
        self.assertIn('home/devops/project/external', manifest['skipped_external_symlinks'])

    def test_tampered_archive_never_gets_verified_marker(self):
        migration.backup(self.args)
        data = bytearray(self.archive.read_bytes())
        data[-20] ^= 1
        self.archive.write_bytes(data)
        target = self.root / 'failed'
        with self.assertRaises((RuntimeError, tarfile.TarError)):
            migration.restore(argparse.Namespace(archive=self.archive, identity=self.identity, into=target))
        self.assertFalse((target / '.verified').exists())

    def test_existing_output_and_recursive_output_are_rejected(self):
        self.archive.write_text('existing')
        with self.assertRaises(ValueError):
            migration.backup(self.args)
        self.assertEqual(self.archive.read_text(), 'existing')
        self.args.output = self.home / 'devops/recursive.age'
        with self.assertRaises(ValueError):
            migration.backup(self.args)

    def test_containers_restarted_if_encryption_fails(self):
        self.args.docker = self.args.stop_containers = True

        def fake_docker(args):
            if args == ['ps', '-aq']:
                return ''
            if args == ['volume', 'ls', '-q']:
                return ''
            if args == ['ps', '-q']:
                return 'container1'
            raise AssertionError(args)

        def fail_age(*args, **kwargs):
            raise OSError('simulated age startup failure')

        with mock.patch.object(migration.os, 'geteuid', return_value=0), \
             mock.patch.object(migration, 'docker', side_effect=fake_docker), \
             mock.patch.object(migration.subprocess, 'run') as run, \
             mock.patch.object(migration.subprocess, 'Popen', side_effect=fail_age):
            with self.assertRaises(OSError):
                migration.backup(self.args)
            self.assertEqual(run.call_args_list, [mock.call([*migration.DOCKER, 'stop', '--time', '60', 'container1'], check=True),
                                                 mock.call([*migration.DOCKER, 'start', 'container1'], check=True)])
        self.assertFalse(self.archive.with_name(self.archive.name + '.partial').exists())


if __name__ == '__main__':
    unittest.main()
