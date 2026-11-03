#!/usr/bin/env python3
"""Copy verified staging onto the NEW workstation; defaults to an rsync dry run."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import re
from relocation import relocate, windows_path


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--staging', required=True, type=Path)
    p.add_argument('--home', required=True, type=Path)
    p.add_argument('--windows-home', type=Path)
    p.add_argument('--volumes', action='store_true')
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    staging, home = a.staging.resolve(), a.home.resolve()
    if not (staging / '.verified').is_file():
        p.error('Staging was not fully authenticated by migration.py restore')
    manifest = json.loads((staging / 'manifest.json').read_text())
    if not home.is_dir() or home.parent != Path('/home'):
        p.error('--home must be an existing /home/<user> directory')
    if str(home) != manifest['source_home']:
        p.error('This migration release preserves the Linux home path and numeric UID. Use the original Linux username; arbitrary home relocation is not supported for inherited scripts.')
    if staging.is_relative_to(home) or home.is_relative_to(staging):
        p.error('Staging and target home must be separate trees')
    if a.apply:
        if os.geteuid() != 0 or not Path('/var/lib/wsl2-workstation/bootstrap-ready').exists():
            p.error('--apply requires sudo and the target bootstrap marker')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    report = staging / ('.deployment-' + ('apply-' if a.apply else 'preview-') + stamp + '.txt')
    copies = [(staging / 'home', home, False)]
    if (staging / 'windows').is_dir():
        if not a.windows_home or not a.windows_home.is_dir() or not re.fullmatch(r'/mnt/[a-z]/Users/[^/]+', str(a.windows_home.resolve())):
            p.error('Windows data is present: supply the existing target --windows-home')
        copies.append((staging / 'windows', a.windows_home.resolve(), True))
    docker = ['docker', '--host', 'unix:///var/run/docker.sock']
    if a.volumes:
        running = subprocess.check_output([*docker, 'ps', '-q'], text=True).strip()
        if running:
            p.error('Stop all target containers before deploying volumes; do not restore into active volumes')
        for v in manifest.get('volumes', []):
            name = v['Name']
            if '/' in name or name in {'', '.', '..'}:
                p.error('Invalid volume name in manifest')
            if v.get('Driver') != 'local' or v.get('Options'):
                p.error('Only ordinary local volumes are supported')
            inspect = subprocess.run([*docker, 'volume', 'inspect', name], capture_output=True, text=True)
            if inspect.returncode:
                if not a.apply:
                    print(f'DRY RUN: would create local volume {name}; contents not compared until it exists')
                    continue
                subprocess.run([*docker, 'volume', 'create', name], check=True)
                inspect = subprocess.run([*docker, 'volume', 'inspect', name], capture_output=True, text=True, check=True)
            target = json.loads(inspect.stdout)[0]
            if target['Driver'] != 'local' or target.get('Options'):
                p.error('Target volume is not an ordinary local volume')
            if any(Path(target['Mountpoint']).iterdir()):
                p.error(f'Volume {name} is not empty. Restore to an empty target; existing database files must not be merged.')
            copies.append((staging / 'volumes' / name, Path(target['Mountpoint']), False))
    elif manifest.get('volumes'):
        print('Volumes are present but NOT selected. Deploy again with --volumes before starting services.')
    for source, target, windows in copies:
        if not source.is_dir():
            p.error(f'Missing staged directory: {source}')
        backup = (target if windows else target.parent) / ('.wsl2-rollback-' + target.name + '-' + stamp)
        args = ['rsync', '-a', '--safe-links', '--backup', f'--backup-dir={backup}']
        # Windows DrvFs commonly does not support Linux ownership/mode changes.
        if windows:
            args += ['--no-owner', '--no-group', '--no-perms', '--omit-dir-times']
            preferences = {
                'AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json': 'terminal.json',
                'AppData/Roaming/Code/User/settings.json': 'code-settings.json',
                'AppData/Roaming/Code/User/keybindings.json': 'code-keybindings.json',
            }
            for relative, filename in preferences.items():
                args.append('--exclude=/' + relative)
                if a.apply and (source / relative).is_file():
                    saved = target / '.wsl2-source-preferences'
                    saved.mkdir(mode=0o700, exist_ok=True)
                    shutil.copyfile(source / relative, saved / filename)
                    old_home = manifest.get('source_windows_home') or ''
                    (saved / 'metadata.json').write_text(json.dumps({'old_windows_home': windows_path(old_home)}) + '\n')
        if not a.apply:
            args.append('--dry-run')
        # Do not log file names: they can themselves contain confidential information.
        with report.open('a') as log:
            subprocess.run([*args, '--itemize-changes', str(source) + '/', str(target) + '/'], stdout=log, check=True)
        print(f'{"APPLIED" if a.apply else "DRY RUN"}: {source.name} -> {target}; overwritten files retained in {backup}')
    if a.windows_home:
        old_windows = manifest.get('source_windows_home') or ''
        configs = [home / name for name in ['.gitconfig', '.terraformrc', '.odbc.ini', '.codex/config.toml', '.config/mcp/mcp.json']]
        configs += [a.windows_home / name for name in ['.aws/config', '.azure/config', '.gitconfig', '.wsl2-source-preferences/code-settings.json', '.wsl2-source-preferences/code-keybindings.json']]
        for path in configs:
            if not path.is_file() or path.is_symlink():
                continue
            original = path.read_text(encoding='utf-8-sig')
            updated = relocate(original, old_windows, str(a.windows_home))
            if updated != original:
                if a.apply:
                    shutil.copy2(path, str(path) + '.wsl2-paths-' + stamp + '.bak')
                    path.write_text(updated)
                print(f'{"APPLIED" if a.apply else "DRY RUN"}: Windows profile references in {path.name}')
    system = staging / 'system/etc'
    for name in ['odbc.ini', 'odbcinst.ini']:
        if (system / name).is_file():
            if a.apply:
                destination = Path('/etc') / name
                if destination.exists():
                    shutil.copy2(destination, str(destination) + '.wsl2-' + stamp + '.bak')
                shutil.copyfile(system / name, destination)
                destination.chmod(0o600 if name == 'odbc.ini' else 0o644)
            print(f'{"APPLIED" if a.apply else "DRY RUN"}: /etc/{name}')
    print('Run Ansible after deployment to reapply portable configuration and recreate Windows cloud links.')
    print(f'Private file change report: {report}')


if __name__ == '__main__':
    main()
