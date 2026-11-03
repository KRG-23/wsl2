import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def test_colleague_configuration_needs_no_private_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'local.yml'
            command = [sys.executable, str(ROOT / 'scripts/configure.py'), '--user', 'alice',
                       '--windows-home', '/mnt/c/Users/Alice Smith', '--without', 'node', '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True)
            values = yaml.safe_load(output.read_text())
            self.assertEqual(values['workstation_profile'], 'base')
            self.assertEqual(values['workstation_user'], 'alice')
            self.assertFalse(values['enable_node'])
            self.assertTrue(values['enable_docker'])
            self.assertNotIn('assets_directory', values)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            before = output.read_bytes()
            rerun = subprocess.run(command, capture_output=True)
            self.assertNotEqual(rerun.returncode, 0)
            self.assertEqual(output.read_bytes(), before)

    def test_invalid_username_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'local.yml'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/configure.py'), '--user', 'root',
                                     '--windows-home', '', '--output', str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_public_asset_lock_has_fixed_revisions_and_digests(self):
        lock = json.loads((ROOT / 'manifests/public-assets.json').read_text())
        for item in lock['assets']:
            self.assertRegex(item['sha256'], r'^[a-f0-9]{64}$')
            self.assertTrue(item['url'].startswith('https://'))
            self.assertNotIn('latest', item['url'])
            self.assertTrue(item['revision'])


if __name__ == '__main__':
    unittest.main()
