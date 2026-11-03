#!/usr/bin/env python3
"""Non-mutating smoke checks; no SSO login, network writes or service starts."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--home', type=Path, default=Path.home())
    p.add_argument('--profile', choices=['base', 'migration'], default='base')
    p.add_argument('--without', action='append', choices=['node', 'terraform', 'uv'], default=[])
    p.add_argument('--cloud-links', action='store_true')
    p.add_argument('--docker', action='store_true')
    p.add_argument('--toolz', action='store_true')
    p.add_argument('--url', action='append', default=[], help='HTTPS URL to check (no bearer tokens)')
    a = p.parse_args()
    checks = []

    def check(name, ok):
        checks.append({'check': name, 'ok': bool(ok)})

    tools = ['zsh', 'git', 'fd', 'bat', 'fzf', 'rg', 'micro', 'ansible', 'pre-commit']
    for name in ['terraform', 'node', 'uv']:
        if name not in a.without:
            tools.append(name)
    if 'node' not in a.without:
        tools.append('npm')
    if a.profile == 'migration':
        tools += ['aws', 'tflint', 'tfautomv', 'python3.12']
    for name in tools:
        check(name, shutil.which(name))
    for config in [a.home / '.zshrc', a.home / '.config/zsh/devops-tools.zsh']:
        r = subprocess.run(['zsh', '-n', str(config)], capture_output=True)
        check(str(config.relative_to(a.home)) + ' syntax', r.returncode == 0)
    for name in ['.aws', '.azure'] if a.cloud_links else []:
        check(name + ' symlink resolves', (a.home / name).is_symlink() and (a.home / name).exists())
    check('systemd PID 1', Path('/proc/1/comm').read_text().strip() == 'systemd')
    for runtime in ['/usr/local/bin/python3.12', '/usr/local/bin/tflint', '/usr/local/bin/terraform-mcp-server']:
        if Path(runtime).exists():
            r = subprocess.run(['ldd', runtime], capture_output=True, text=True)
            check(runtime + ' shared libraries', 'not found' not in r.stdout)
    if a.docker:
        for args in [['info', '--format', '{{.ServerVersion}}'], ['compose', 'version']]:
            r = subprocess.run(['docker', '--host', 'unix:///var/run/docker.sock', *args], capture_output=True)
            check('docker ' + args[0], r.returncode == 0)
    if a.toolz:
        for name in ['bin/codex-vault', 'bin/codex-mcp-secret', 'docker-tools/vault/local/ensure.sh']:
            check('Toolz/' + name, os.access(a.home / 'devops/Toolz' / name, os.X_OK))
    for url in a.url:
        if not url.startswith('https://') or '@' in url or '?' in url:
            p.error('Use a public HTTPS endpoint without credentials or query parameters')
        r = subprocess.run(['curl', '--silent', '--fail', '--head', '--max-time', '15', url], capture_output=True)
        check('HTTPS endpoint ' + str(a.url.index(url) + 1), r.returncode == 0)
    print(json.dumps(checks, indent=2))
    return 0 if all(c['ok'] for c in checks) else 1


if __name__ == '__main__':
    sys.exit(main())
