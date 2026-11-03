import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from docker_state import inspect_state, compose_groups


class DockerStateTests(unittest.TestCase):
    def test_snapshot_records_image_digests_but_never_environment(self):
        raw = [{'Name': '/db', 'Image': 'sha256:abc', 'State': {'Running': True}, 'Mounts': [],
                'Config': {'Image': 'postgres:latest', 'Env': ['PASSWORD=SECRET-CANARY'],
                           'Labels': {'com.docker.compose.project': 'project', 'com.docker.compose.service': 'db',
                                      'com.docker.compose.project.config_files': '/home/user/compose.yml',
                                      'arbitrary.secret': 'SECRET-CANARY'}}}]
        def command(args):
            if args == ['ps', '-aq']:
                return 'container1'
            if args[0] == 'inspect':
                return json.dumps(raw)
            return json.dumps([{'Id': 'sha256:abc', 'RepoDigests': ['postgres@sha256:fixed']}])
        state = inspect_state(command)
        self.assertNotIn('SECRET-CANARY', json.dumps(state))
        groups = compose_groups(state)
        self.assertEqual(groups['project']['services']['db'], {'image': 'postgres@sha256:fixed', 'pull_policy': 'missing'})

    def test_local_built_images_must_exist_and_stopped_services_are_skipped(self):
        labels = {'project': 'project', 'service': 'app', 'project.config_files': '/home/user/compose.yml'}
        containers = [{'name': 'app', 'image_id': 'sha256:local', 'running': True, 'compose': labels},
                      {'name': 'stopped', 'image_id': 'sha256:local', 'running': False, 'compose': {**labels, 'service': 'stopped'}}]
        group = compose_groups({'containers': containers, 'images': {'sha256:local': {'repo_digests': []}}})['project']
        self.assertEqual(group['services'], {'app': {'image': 'sha256:local', 'pull_policy': 'never'}})


if __name__ == '__main__':
    unittest.main()
