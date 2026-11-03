#!/usr/bin/env python3
"""Create a private per-user configuration; never provision the machine."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import yaml


def discover_windows_home():
    try:
        value = subprocess.check_output(['cmd.exe', '/c', 'echo', '%USERPROFILE%'], stderr=subprocess.DEVNULL, timeout=5).decode().strip()
        return subprocess.check_output(['wslpath', '-u', value], text=True, timeout=5).strip()
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return ''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--user', required=True, help='Linux target user; will be created if absent')
    p.add_argument('--windows-home', default=None)
    p.add_argument('--profile', choices=['base', 'migration'], default='base')
    p.add_argument('--git-name', default='')
    p.add_argument('--git-email', default='')
    p.add_argument('--without', action='append', choices=['docker', 'terraform', 'node', 'uv'], default=[])
    p.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'inventory/local.yml')
    a = p.parse_args()
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', a.user) or a.user == 'root':
        p.error('Choose a regular Linux username, not root')
    windows = discover_windows_home() if a.windows_home is None else a.windows_home
    if windows and not re.fullmatch(r'/mnt/[a-z]/Users/[^/]+', windows):
        p.error('--windows-home must be /mnt/<drive>/Users/<username>')
    config = {'workstation_profile': a.profile, 'workstation_user': a.user, 'windows_home': windows,
              'git_name': a.git_name, 'git_email': a.git_email}
    for module in ['docker', 'terraform', 'node', 'uv']:
        config['enable_' + module] = module not in a.without
    os.umask(0o077)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as f:
        yaml.safe_dump(config, f, sort_keys=True)
    print(f'Private configuration created: {a.output}. Review it before provisioning.')


if __name__ == '__main__':
    main()
