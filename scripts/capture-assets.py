#!/usr/bin/env python3
"""Capture installed public tools, runtime archives and public CA; never credentials."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tarfile
import yaml


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'private/assets')
    parser.add_argument('--include-informix', action='store_true', help='Capture licensed /opt/IBM/informix privately; never redistribute')
    a = parser.parse_args()
    os.umask(0o077)
    out = a.output.resolve()
    if out.exists():
        parser.error('Asset directory exists; capture to a new directory.')
    out.mkdir(parents=True)
    manifest = {'schema': 1, 'assets': [], 'missing': []}

    def record(path, destination, scope='system', kind='binary'):
        manifest['assets'].append({'file': path.name, 'sha256': digest(path), 'destination': destination,
                                   'scope': scope, 'kind': kind})

    for source, dest, scope in [
        ('/usr/local/bin/tflint', '/usr/local/bin/tflint', 'system'),
        ('/usr/local/bin/tfautomv', '/usr/local/bin/tfautomv', 'system'),
        ('/usr/local/bin/terraform-mcp-server', '/usr/local/bin/terraform-mcp-server', 'system'),
        (str(a.home / 'go/bin/mcp-grafana'), 'go/bin/mcp-grafana', 'home'),
        (str(a.home / '.local/bin/uv'), '.local/bin/uv', 'home'),
        (str(a.home / '.local/bin/uvx'), '.local/bin/uvx', 'home')]:
        p = Path(source)
        if p.is_file():
            target = out / p.name
            shutil.copyfile(p, target)
            record(target, dest, scope)
        else:
            manifest['missing'].append(source)

    # Only installed runtime files. Python site-packages are private artifacts, not Git content.
    runtimes = [('/usr/local/aws-cli', '/usr/local/aws-cli'),
                                ('/usr/local/sessionmanagerplugin', '/usr/local/sessionmanagerplugin'),
                                ('/usr/local/lib/python3.12', '/usr/local/lib/python3.12')]
    if a.include_informix:
        runtimes.append(('/opt/IBM/informix', '/opt/IBM/informix'))
        runtimes.append(('/usr/local/ibm/gsk8_64', '/usr/local/ibm/gsk8_64'))
    for source, destination in runtimes:
        p = Path(source)
        if p.is_dir():
            archive = out / (p.name + '.tar.gz')
            with tarfile.open(archive, 'w:gz', compresslevel=3) as tar:
                for child in sorted(p.iterdir()):
                    if a.include_informix and source == '/opt/IBM/informix' and child.name in {'tmp', 'logs'}:
                        continue
                    tar.add(child, arcname=child.name, filter=lambda info: None if '__pycache__' in info.name.split('/') else info)
            record(archive, destination, kind='archive')
        else:
            manifest['missing'].append(source)
    for p in [Path('/usr/local/bin/python3.12'), *Path('/usr/local/lib').glob('libpython3.12*.so*')]:
        if p.is_file():
            target = out / p.name
            shutil.copyfile(p, target)
            record(target, str(p))

    # git archive excludes local untracked files and credentials in .git/config.
    omz = a.home / '.oh-my-zsh'
    if (omz / '.git').is_dir():
        archive = out / 'oh-my-zsh.tar.gz'
        subprocess.run(['git', '-C', str(omz), 'archive', '--format=tar.gz', f'--output={archive}', 'HEAD'], check=True)
        manifest['oh_my_zsh_commit'] = subprocess.check_output(['git', '-C', str(omz), 'rev-parse', 'HEAD'], text=True).strip()
        record(archive, '.oh-my-zsh', 'home', 'archive')
    else:
        manifest['missing'].append(str(omz))

    versions = {}
    node = subprocess.run(['node', '--version'], capture_output=True, text=True)
    if node.returncode == 0:
        versions['node_major'] = node.stdout.strip().lstrip('v').split('.')[0]
    packages = {'claude_version': Path('/usr/local/lib/node_modules/@anthropic-ai/claude-code/package.json'),
                'yarn_version': Path('/usr/local/lib/node_modules/yarn/package.json'),
                'codex_version': Path('/usr/lib/node_modules/@openai/codex/package.json')}
    for key, path in packages.items():
        if path.is_file():
            versions[key] = json.loads(path.read_text())['version']
    metadata = a.home / '.local/pipx/venvs/pre-commit/pipx_metadata.json'
    if metadata.is_file():
        versions['pre_commit_version'] = json.loads(metadata.read_text())['main_package']['package_version']
    (out / 'versions.yml').write_text(yaml.safe_dump(versions, sort_keys=True))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')

    ca = out.parent / 'ca'
    ca.mkdir(exist_ok=True)
    for p in Path('/usr/local/share/ca-certificates').iterdir():
        if p.is_file() and b'-----BEGIN CERTIFICATE-----' in p.read_bytes() and b'PRIVATE KEY' not in p.read_bytes():
            # update-ca-certificates requires a .crt suffix.
            name = p.name if p.name.endswith('.crt') else p.name + '.crt'
            shutil.copyfile(p, ca / name)
    # Write personal values only into the ignored inventory, never into Git.
    local = Path(__file__).resolve().parents[1] / 'inventory/local.yml'
    values = yaml.safe_load(local.read_text()) if local.exists() else {}
    values.setdefault('workstation_user', a.home.name)
    values.setdefault('workstation_profile', 'migration')
    values.setdefault('windows_home', '')
    repo = Path(__file__).resolve().parents[1]
    values['assets_directory'] = '{{ playbook_dir }}/' + str(out.relative_to(repo)) if out.is_relative_to(repo) else str(out)
    values.setdefault('enable_bedrock', 'CLAUDE_CODE_USE_BEDROCK=1' in (a.home / '.bashrc').read_text() if (a.home / '.bashrc').exists() else False)
    values.setdefault('enable_aws_windows_link', (a.home / '.aws').is_symlink())
    values.setdefault('enable_azure_windows_link', (a.home / '.azure').is_symlink())
    values.setdefault('enable_corporate_ca', any(ca.glob('*.crt')))
    aws = a.home / '.aws'
    if aws.is_symlink():
        if not values['windows_home']:
            values['windows_home'] = str(aws.resolve().parent)
    for key in ['user.name', 'user.email']:
        result = subprocess.run(['git', 'config', '--global', '--get', key], capture_output=True, text=True)
        if result.returncode == 0:
            values.setdefault('git_name' if key == 'user.name' else 'git_email', result.stdout.strip())
    source_shell = a.home / '.config/zsh/devops-tools.zsh'
    if source_shell.exists():
        match = re.search(r'^\s+(\w+@[A-Za-z0-9.-]+)\s*$', source_shell.read_text(), re.M)
        if match:
            values.setdefault('bastion_ssh_target', match.group(1))
    zshrc = a.home / '.zshrc'
    if zshrc.is_file():
        match = re.search(r'\$HOME/([^"\n:]+):/docs', zshrc.read_text())
        if match:
            values.setdefault('zensical_docs_directory', '{{ workstation_home }}/' + match.group(1))
    local.write_text(yaml.safe_dump(values, sort_keys=True))
    local.chmod(0o600)
    print(f'Captured {len(manifest["assets"])} assets in {out}; missing: {len(manifest["missing"])}. See manifest.json.')
    print('Keep private/ outside Git. Encrypt it with migration.py backup before transfer.')


if __name__ == '__main__':
    main()
