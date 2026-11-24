"""The minimal local config must inherit role defaults with an explicit inventory."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('ansible-inventory'), 'Ansible CLI required')
class InventoryLoadingTest(unittest.TestCase):
    def test_explicit_inventory_survives_ignored_config_with_minimal_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            # Model a Windows mount where automatic ansible.cfg discovery is refused.
            work.chmod(0o777)
            shutil.copyfile(ROOT / 'ansible.cfg', work / 'ansible.cfg')
            (work / 'inventory').symlink_to(ROOT / 'inventory', target_is_directory=True)
            local = work / 'local.yml'
            subprocess.run([sys.executable, str(ROOT / 'scripts/configure.py'),
                            '--user', 'alice', '--windows-home', '/mnt/c/Users/Alice',
                            '--without', 'docker', '--output', str(local)],
                           check=True, capture_output=True, timeout=15)
            env = {**os.environ, 'ANSIBLE_LOCAL_TEMP': str(work / 'ansible-tmp')}
            env.pop('ANSIBLE_CONFIG', None)
            env.pop('ANSIBLE_INVENTORY', None)

            def inventory(extra):
                result = subprocess.run(['ansible-inventory', *extra, '--host', 'localhost',
                                         '-e', '@' + str(local)], cwd=work, env=env,
                                        text=True, capture_output=True, check=True, timeout=30)
                return json.loads(result.stdout)

            implicit = inventory([])
            self.assertEqual(implicit['workstation_user'], 'alice')
            self.assertNotIn('workstation_home', implicit)
            self.assertNotIn('base_apt_packages', implicit)
            explicit = inventory(['-i', str(ROOT / 'inventory/hosts.yml')])
            for key in ['workstation_home', 'workstation_uid', 'workstation_gid',
                        'base_apt_packages', 'enable_corporate_ca', 'workstation_timezone']:
                self.assertIn(key, explicit)
            self.assertEqual(explicit['workstation_user'], 'alice')
            self.assertFalse(explicit['enable_docker'])
            self.assertTrue(explicit['enable_node'])


if __name__ == '__main__':
    unittest.main()
