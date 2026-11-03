#!/usr/bin/env python3
"""Preview or restart recorded Compose services using their original image digests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from docker_state import compose_groups


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--staging', required=True, type=Path)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--phase', choices=['all', 'vault', 'applications'], default='all')
    a = p.parse_args()
    if not (a.staging / '.verified').is_file():
        p.error('Use fully authenticated restore staging')
    manifest = json.loads((a.staging / 'manifest.json').read_text())
    if 'docker_state' not in manifest:
        p.error('Snapshot has no Docker metadata; recreate Compose services manually')
    groups = compose_groups(manifest['docker_state'])
    def is_vault(group):
        return any('hashicorp/vault@' in service['image'] for service in group['services'].values())
    groups = {name: group for name, group in groups.items() if a.phase == 'all' or (is_vault(group) if a.phase == 'vault' else not is_vault(group))}
    groups = dict(sorted(groups.items(), key=lambda item: not is_vault(item[1])))
    docker = ['docker', '--host', 'unix:///var/run/docker.sock']
    if a.apply and not Path('/var/lib/wsl2-workstation/bootstrap-ready').is_file():
        p.error('Apply is only permitted on the bootstrapped target')
    # Preflight every project before starting anything.
    for project, group in groups.items():
        if not all(Path(f).is_file() and Path(f).is_absolute() for f in group['files']):
            p.error(f'Restored Compose files missing for project {project}')
        for service in group['services'].values():
            if a.apply and service['pull_policy'] == 'never':
                check = subprocess.run([*docker, 'image', 'inspect', service['image']], capture_output=True)
                if check.returncode:
                    p.error('A source-built image is missing; restore its encrypted docker image save archive first')
    os.umask(0o077)
    home = Path(manifest['source_home'])
    lock_directory = home / '.config/workstation/compose-locks'
    if a.apply:
        if home.parent != Path('/home') or not (home / '.config/workstation').is_dir():
            p.error('Complete target provisioning before restarting services')
        lock_directory.mkdir(mode=0o700, exist_ok=True)
        os.chown(lock_directory, home.stat().st_uid, home.stat().st_gid)
    for project, group in groups.items():
        print(f'{"APPLY" if a.apply else "PREVIEW"}: Compose project {project}, {len(group["services"])} originally active services, image digests locked')
        if not a.apply:
            continue
        name = hashlib.sha256(project.encode()).hexdigest()[:16] + '.json'
        override = lock_directory / name
        override.write_text(json.dumps({'services': group['services']}, indent=2) + '\n')
        os.chown(override, home.stat().st_uid, home.stat().st_gid)
        args = [*docker, 'compose', '--project-name', project]
        if group['directory']:
            args += ['--project-directory', group['directory']]
        for f in group['files']:
            args += ['--file', f]
        if str(override.resolve()) not in group['files']:
            args += ['--file', str(override.resolve())]
        args += ['up', '-d', '--no-build', '--no-deps', *group['services']]
        subprocess.run(args, check=True, env={**os.environ, 'HOME': str(home), 'USER': home.name, 'LOGNAME': home.name})
    print('Transient containers without Compose metadata are not restarted; reconnect the corresponding client tools.')


if __name__ == '__main__':
    main()
