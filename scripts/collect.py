#!/usr/bin/env python3
"""Read-only inventory. No environment, credentials, remote URLs or config contents."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
from docker_state import inspect_state


def run(argv, timeout=30):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"ok": p.returncode == 0, "output": p.stdout.strip() if p.returncode == 0 else "", "exit": p.returncode}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": type(e).__name__}


def extensions(directory):
    result = set()
    if directory.is_dir():
        for p in directory.glob('*/package.json'):
            try:
                d = json.loads(p.read_text())
                result.add(f"{d['publisher']}.{d['name']}")
            except (OSError, ValueError, KeyError):
                pass
    return sorted(result)


def git_workspaces(root):
    result = []
    if not root.is_dir():
        return result
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '.terraform', '.venv', '__pycache__', '.cache'}]
        if '.git' in files or (Path(directory) / '.git').is_dir():
            status = run(['git', '-C', directory, 'status', '--porcelain=v1', '-uno'])
            untracked = run(['git', '-C', directory, 'ls-files', '--others', '--exclude-standard'])
            result.append({'path': str(Path(directory).relative_to(root)),
                           'tracked_changes': len(status.get('output', '').splitlines()),
                           'untracked_files': len(untracked.get('output', '').splitlines()),
                           'readable': status['ok'] and untracked['ok']})
    return sorted(result, key=lambda x: x['path'])


def collect(home, windows_home=None, projects=None):
    package_result = run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${db:Status-Status}\n'])
    packages = {}
    for line in package_result.get('output', '').splitlines():
        parts = line.split('\t')
        if len(parts) == 3 and parts[2] == 'installed':
            packages[parts[0]] = parts[1]
    tools = {}
    for name, args in {'git': ['--version'], 'zsh': ['--version'], 'ansible': ['--version'],
                       'terraform': ['version', '-json'], 'node': ['--version'], 'npm': ['--version'],
                       'python3': ['--version'], 'python3.12': ['--version'], 'uv': ['--version'],
                       'go': ['version'], 'aws': ['--version'], 'tflint': ['--version'],
                       'tfautomv': ['--version'], 'session-manager-plugin': ['--version']}.items():
        exe = shutil.which(name)
        tools[name] = {'path': exe, **(run([exe, *args]) if exe else {'ok': False})}
    config = {}
    for path in [home / '.zshrc', home / '.bashrc', home / '.profile', home / '.vimrc',
                 home / '.config/zsh/devops-tools.zsh', Path('/etc/wsl.conf'), Path('/etc/default/locale')]:
        if path.is_file():
            config[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    checks = {}
    for name in ['.ssh', '.gnupg', '.password-store', '.config/secrets', '.codex', '.claude', '.git-credentials']:
        p = home / name
        checks[name] = {'present': p.exists(), 'readable': os.access(p, os.R_OK)}
    docker = {}
    for name, args in [('context', ['context', 'show']),
                       ('containers', ['--host', 'unix:///var/run/docker.sock', 'ps', '-a', '--format', '{{.Names}}\t{{.Image}}\t{{.Status}}']),
                       ('volumes', ['--host', 'unix:///var/run/docker.sock', 'volume', 'ls', '--format', '{{.Name}}'])]:
        docker[name] = run(['docker', *args])
    if docker['containers']['ok']:
        try:
            docker['state'] = inspect_state(lambda args: subprocess.check_output(['docker', '--host', 'unix:///var/run/docker.sock', *args], text=True, stderr=subprocess.DEVNULL, timeout=30).strip())
        except (subprocess.SubprocessError, OSError, ValueError, KeyError) as e:
            docker['state'] = {'error': type(e).__name__}
    ca = []
    for p in Path('/usr/local/share/ca-certificates').glob('*'):
        if p.is_file():
            ca.append({'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    result = {'schema': 1, 'collected_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'os_release': dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line),
              'architecture': run(['uname', '-m']), 'kernel': run(['uname', '-r']),
              'packages': packages, 'package_inventory_ok': package_result['ok'],
              'manual_packages': run(['apt-mark', 'showmanual']), 'tools': tools,
              'npm': run(['npm', 'ls', '-g', '--depth=0', '--json']),
              'pipx': run(['pipx', 'list', '--json']), 'config_sha256': config,
              'sensitive_locations': checks, 'corporate_ca': ca,
              'services_enabled': run(['systemctl', 'list-unit-files', '--state=enabled', '--no-pager']),
              'services_active': run(['systemctl', 'list-units', '--state=active', '--no-pager']),
              'docker': docker, 'git_workspaces': git_workspaces(projects or home / 'devops'),
              'vscode_wsl_extensions': extensions(home / '.vscode-server/extensions'),
              'windows_links': {s: os.readlink(home / s) for s in ['.aws', '.azure'] if (home / s).is_symlink()}}
    if windows_home:
        result['vscode_windows_extensions'] = extensions(windows_home / '.vscode/extensions')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--home', type=Path, default=Path.home())
    p.add_argument('--windows-home', type=Path)
    p.add_argument('--projects', type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    os.umask(0o077)
    if a.output.exists():
        p.error('Output exists; use a new filename.')
    data = collect(a.home, a.windows_home, a.projects)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write('\n')
    print(f'Private inventory: {a.output}; {len(data["packages"])} packages. Review before sharing.')


if __name__ == '__main__':
    main()
