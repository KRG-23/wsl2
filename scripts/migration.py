#!/usr/bin/env python3
"""Stream encrypted backups; restore only to a new, private staging directory."""
import argparse
import datetime
import io
import json
import os
import posixpath
import signal
from pathlib import Path, PurePosixPath
import pwd
import shutil
import subprocess
import sys
import tarfile
from docker_state import inspect_state

DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']
HOME_ITEMS = ['devops', '.ssh', '.gnupg', '.password-store', '.config', '.gitconfig',
              '.git-credentials', '.my-credentials', '.terraformrc', '.zshrc', '.bashrc',
              '.profile', '.vimrc', '.codex', '.claude', '.claude.json', '.copilot',
              '.mcp-auth', '.gitlab', '.putty', '.odbc.ini', '.informix', '.zsh_history',
              '.bash_history', 'aap-keys', 'certs', 'informix-csdk-install', 'export',
              'challenge', 'net-monitor', 'FBC.md', 'KeepTeamsActive.ahk', '.terraform.d',
              '.tflint.hcl', '.docker/config.json', '.docker/mcp', '.redhat', '.sigstore',
              '.local/bin/env', '.local/bin/env.fish', '.local/share/powershell',
              '.local/share/NuGet', '.local/share/mcp', '.local/share/fastmcp', '.dotnet',
              '.npmrc', '.pypirc', '.netrc', '.kube', '.vscode-server/data/Machine/settings.json']
WINDOWS_ITEMS = ['.aws', '.azure', '.ssh', '.gitconfig', 'AppData/Roaming/Code/User/settings.json',
                 'AppData/Roaming/Code/User/keybindings.json', 'AppData/Roaming/Code/User/snippets',
                 'AppData/Local/Microsoft/Windows/Fonts',
                 'AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json',
                 'Downloads/futuristic-background-with-green-letters.jpg']
EXCLUDED_PARTS = {'node_modules', '__pycache__', '.terraform', '.venv', '.pytest_cache',
                  '.mypy_cache', '.ruff_cache', '.cache', '.cursor-server', 'plugin-cache'}


def docker(args):
    return subprocess.check_output([*DOCKER, *args], text=True).strip()


def running_containers():
    return docker(['ps', '-q']).splitlines()


def backup_filter(info):
    parts = PurePosixPath(info.name).parts
    # Never apply developer cache exclusions to database volumes or Windows data.
    if parts[0] == 'home' and any(p in EXCLUDED_PARTS for p in parts):
        return None
    if info.isdev() or info.isfifo():
        return None
    # Never recursively include generated backups/staging or local caches.
    if parts[:2] == ('home', '.codex') and (info.name.endswith('-shm') or any(p in {'tmp', 'cache', 'shell_snapshots', 'ipc', 'process_manager', 'app-server-daemon', 'thread-writer-locks'} for p in parts)):
        return None
    return info


def check_member(info, destination):
    # Explicit traversal guard is also exercised by unit tests; data_filter checks
    # symlink and hardlink escapes against previously extracted members.
    parts = PurePosixPath(info.name).parts
    if info.name.startswith('/') or '..' in parts or not parts or parts[0] not in {'home', 'windows', 'volumes', 'system', 'manifest.json'}:
        raise ValueError(f'Unsafe archive member: {info.name}')
    if parts[0] == 'system' and info.name not in {'system/etc/odbc.ini', 'system/etc/odbcinst.ini'}:
        raise ValueError('Only approved ODBC system configuration may be restored')
    if info.isdev() or info.isfifo():
        raise ValueError('Special files are forbidden')
    filtered = tarfile.data_filter(info, destination)
    # The staging directory is private; preserve numeric ownership for database
    # volumes when restoring as root, without permitting setuid or device files.
    if filtered:
        mode = info.mode & 0o1777 if info.isdir() else filtered.mode
        return filtered.replace(uid=info.uid, gid=info.gid, uname=None, gname=None, mode=mode)
    return None


def user_home():
    return Path(pwd.getpwnam(os.environ['SUDO_USER']).pw_dir) if os.environ.get('SUDO_USER') else Path.home()


def backup(a):
    if not a.acknowledge_quiesced:
        raise ValueError('Close editors/agents and stop non-Docker writers; then pass --acknowledge-quiesced. This script does not freeze databases or active SQLite writers.')
    output = a.output.resolve()
    if output.exists():
        raise ValueError('Output already exists')
    if not a.recipient.startswith('age1'):
        raise ValueError('Use an age public recipient (age1...), never a private key')
    if not shutil.which('age'):
        raise ValueError('Install age first')
    home = a.home.resolve()
    repo = Path(__file__).resolve().parents[1]
    artifacts_prefix = 'home/' + str(repo.relative_to(home) / 'artifacts') if repo.is_relative_to(home) else None
    roots = []
    for name in HOME_ITEMS:
        p = home / name
        if p.exists() or p.is_symlink():
            roots.append((p, 'home/' + name))
    # Top-level private certificates outside certs/ were observed on the source.
    for p in sorted(home.iterdir()):
        if p.is_file() and p.suffix.lower() in {'.pfx', '.p12', '.crt', '.cer', '.key', '.pem'}:
            roots.append((p, 'home/' + p.name))
    for name in a.extra_home:
        p = Path(name)
        if p.is_absolute() or '..' in p.parts or not p.parts:
            raise ValueError('--extra-home must be relative to the Linux home')
        if not (home / p).exists():
            raise ValueError(f'Missing extra home path: {p}')
        roots.append((home / p, 'home/' + p.as_posix()))
    for name in ['/etc/odbc.ini', '/etc/odbcinst.ini'] if a.system_odbc else []:
        source = Path(name)
        if source.is_file():
            roots.append((source, 'system' + name))
    if a.windows_home:
        for name in WINDOWS_ITEMS:
            p = a.windows_home / name
            if p.exists():
                roots.append((p, 'windows/' + name))
    # A ciphertext inside any included tree would recurse into itself.
    for source, _ in roots:
        if source.is_dir() and output.is_relative_to(source.resolve()):
            raise ValueError(f'Place --output outside included directories: {source}')
    stopped, volumes, mounts = [], [], []
    state = {'containers': [], 'images': {}}
    ignored_binds = {str(Path(p).resolve()) for p in a.ignore_bind}
    if any(not Path(p).is_absolute() for p in a.ignore_bind):
        raise ValueError('--ignore-bind must be an absolute source path; inspect its contents before excluding it')
    skipped_links = []

    def portable_filter(info):
        if artifacts_prefix and (info.name == artifacts_prefix or info.name.startswith(artifacts_prefix + '/')):
            return None
        info = backup_filter(info)
        if info is None:
            return None
        if info.issym():
            link = info.linkname
            if link.startswith(str(home) + '/'):
                target = 'home/' + link[len(str(home)) + 1:]
            elif a.windows_home and link.startswith(str(a.windows_home) + '/'):
                target = 'windows/' + link[len(str(a.windows_home)) + 1:]
            elif link.startswith('/'):
                if info.name.startswith('volumes/'):
                    raise ValueError('A volume contains an external absolute symlink; use an application-aware export instead')
                skipped_links.append(info.name)
                return None
            else:
                target = posixpath.normpath(posixpath.join(posixpath.dirname(info.name), link))
            if target.split('/')[0] not in {'home', 'windows', 'volumes'}:
                if info.name.startswith('volumes/'):
                    raise ValueError('A volume symlink escapes the archive; use an application-aware export instead')
                skipped_links.append(info.name)
                return None
            if info.name.startswith('volumes/'):
                volume_root = '/'.join(info.name.split('/')[:2])
                if target != volume_root and not target.startswith(volume_root + '/'):
                    raise ValueError('A volume symlink leaves its volume; use an application-aware export instead')
            info.linkname = posixpath.relpath(target, posixpath.dirname(info.name))
        return info
    age_process = None
    partial = output.with_name(output.name + '.partial')
    if partial.exists():
        raise ValueError('Partial output exists; investigate it before retrying')
    try:
        if a.docker:
            if os.geteuid() != 0:
                raise ValueError('--docker needs sudo to read local volume mountpoints')
            if not a.stop_containers:
                raise ValueError('--docker requires --stop-containers: all currently running local containers will be stopped and restarted')
            state = inspect_state(docker)
            mounts = [{'container': c['name'], 'mounts': c['mounts']} for c in state['containers']]
            names = docker(['volume', 'ls', '-q']).splitlines()
            volumes = json.loads(docker(['volume', 'inspect', *names])) if names else []
            for v in volumes:
                if v['Driver'] != 'local' or v.get('Options'):
                    raise ValueError(f'Volume {v["Name"]} uses external storage/options; export it with its application-specific procedure')
                source = Path(v['Mountpoint'])
                if not source.is_dir() or not os.access(source, os.R_OK):
                    raise ValueError(f'Unreadable local volume: {v["Name"]}')
                roots.append((source, 'volumes/' + v['Name']))
            # Bind mounts outside the selected paths must never disappear silently.
            included = [p.resolve() for p, _ in roots]
            for container in mounts:
                for m in container['mounts']:
                    if m['Type'] != 'bind':
                        continue
                    source = Path(m['Source']).resolve()
                    if str(source) in ignored_binds:
                        continue
                    if not any(source == p or source.is_relative_to(p) for p in included):
                        raise ValueError(f'Uncovered bind mount: {source}. Add it under home with --extra-home, or export it separately and explicitly acknowledge with --ignore-bind PATH.')
            for source, _ in roots:
                if source.is_dir() and output.is_relative_to(source.resolve()):
                    raise ValueError('Backup output cannot be inside a volume or another included directory')
            stopped = running_containers()
            if stopped:
                subprocess.run([*DOCKER, 'stop', '--time', '60', *stopped], check=True)
        manifest = {'schema': 1, 'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'source_home': str(home), 'source_windows_home': str(a.windows_home) if a.windows_home else None,
                    'included': [n for _, n in roots], 'volumes': volumes, 'mounts': mounts, 'docker_state': state,
                    'excluded_parts_in_home': sorted(EXCLUDED_PARTS), 'ignored_binds': sorted(ignored_binds),
                    'quiescence_acknowledged': True}
        output.parent.mkdir(parents=True, exist_ok=True)
        with partial.open('xb') as ciphertext:
            age_process = subprocess.Popen(['age', '-r', a.recipient], stdin=subprocess.PIPE, stdout=ciphertext)
            try:
                with tarfile.open(fileobj=age_process.stdin, mode='w|gz', dereference=False) as tar:
                    for source, name in roots:
                        tar.add(source, arcname=name, filter=portable_filter)
                    manifest['skipped_external_symlinks'] = skipped_links
                    data = json.dumps(manifest, indent=2).encode()
                    info = tarfile.TarInfo('manifest.json')
                    info.mode, info.size = 0o600, len(data)
                    tar.addfile(info, io.BytesIO(data))
            finally:
                age_process.stdin.close()
            if age_process.wait() != 0:
                raise RuntimeError('age encryption failed')
            ciphertext.flush()
            os.fsync(ciphertext.fileno())
        # Do not publish a partial snapshot, even when restarting a container fails.
        if stopped:
            subprocess.run([*DOCKER, 'start', *stopped], check=True)
            stopped = []
        partial.rename(output)
        print(f'Encrypted backup: {output}')
    finally:
        if age_process and age_process.poll() is None:
            age_process.kill()
            age_process.wait()
        if stopped:
            subprocess.run([*DOCKER, 'start', *stopped], check=True)
        if partial.exists():
            partial.unlink()


def restore(a):
    if a.into.exists():
        raise ValueError('Staging destination must not exist. Never extract onto a live home.')
    a.into.mkdir(parents=True, mode=0o700)
    process = subprocess.Popen(['age', '-d', '-i', str(a.identity), str(a.archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|gz') as tar:
            for member in tar:
                tar.extract(member, path=a.into, filter=check_member)
        # Read to EOF so age can authenticate the complete encrypted stream.
        while process.stdout.read(1024 * 1024):
            pass
        if process.wait() != 0:
            raise RuntimeError('Decryption/authentication failed; staging is incomplete')
        manifest = json.loads((a.into / 'manifest.json').read_text())
        if manifest.get('schema') != 1:
            raise ValueError('Unsupported backup schema')
        (a.into / '.verified').write_text('age authenticated; archive paths checked\n')
        print(f'Restored to private staging {a.into}. Review manifest.json, then use deploy-restored.py.')
    except BaseException:
        # A failed/truncated backup must never look deployable.
        print(f'Restore failed; incomplete private staging remains at {a.into}', file=sys.stderr)
        raise
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
        process.wait()


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    b = commands.add_parser('backup')
    b.add_argument('--home', type=Path, default=user_home())
    b.add_argument('--windows-home', type=Path)
    b.add_argument('--recipient', required=True)
    b.add_argument('--output', required=True, type=Path)
    b.add_argument('--extra-home', action='append', default=[])
    b.add_argument('--system-odbc', action='store_true')
    b.add_argument('--ignore-bind', action='append', default=[], metavar='PATH', help='Explicitly omit a bind mount that is disposable or backed up separately; recorded in manifest')
    b.add_argument('--acknowledge-quiesced', action='store_true')
    b.add_argument('--docker', action='store_true')
    b.add_argument('--stop-containers', action='store_true')
    r = commands.add_parser('restore')
    r.add_argument('archive', type=Path)
    r.add_argument('--identity', required=True, type=Path)
    r.add_argument('--into', required=True, type=Path)
    a = p.parse_args()
    # SIGINT already raises KeyboardInterrupt; handle SIGTERM likewise so cleanup
    # can restart containers. Power loss / SIGKILL still require manual recovery.
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        (backup if a.command == 'backup' else restore)(a)
    except (ValueError, OSError, subprocess.SubprocessError, tarfile.TarError, RuntimeError) as e:
        p.exit(1, f'{type(e).__name__}: {e}\n')


if __name__ == '__main__':
    main()
