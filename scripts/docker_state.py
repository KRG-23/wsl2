"""Inspect reproducible container metadata without exporting environment secrets."""
import json


def inspect_state(command):
    ids = command(['ps', '-aq']).splitlines()
    if not ids:
        return {'containers': [], 'images': {}}
    raw = json.loads(command(['inspect', *ids]))
    containers = []
    for c in raw:
        labels = c['Config'].get('Labels') or {}
        containers.append({'name': c['Name'].lstrip('/'), 'image_id': c['Image'], 'image_ref': c['Config']['Image'],
                           'running': c['State']['Running'], 'mounts': c['Mounts'],
                           'compose': {key.removeprefix('com.docker.compose.'): value for key, value in labels.items()
                                       if key in {'com.docker.compose.project', 'com.docker.compose.service',
                                                  'com.docker.compose.project.working_dir', 'com.docker.compose.project.config_files'}}})
    image_ids = sorted({c['image_id'] for c in containers})
    images = {i['Id']: {'repo_digests': i.get('RepoDigests') or []} for i in json.loads(command(['image', 'inspect', *image_ids]))}
    return {'containers': containers, 'images': images}


def compose_groups(state):
    groups = {}
    for c in state['containers']:
        labels = c.get('compose', {})
        if not c['running'] or not labels.get('project') or not labels.get('service'):
            continue
        files = labels.get('project.config_files', '').split(',')
        if not files or not all(files):
            raise ValueError('Compose files missing from container metadata')
        project = labels['project']
        group = groups.setdefault(project, {'files': files, 'directory': labels.get('project.working_dir'), 'services': {}})
        if group['files'] != files:
            raise ValueError('Conflicting Compose files in one project')
        digests = state['images'][c['image_id']]['repo_digests']
        image = digests[0] if digests else c['image_id']
        service = {'image': image, 'pull_policy': 'missing' if digests else 'never'}
        previous = group['services'].setdefault(labels['service'], service)
        if previous != service:
            raise ValueError('Multiple image versions for a single Compose service')
    return groups
