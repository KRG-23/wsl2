#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} != --target-new-distro ]]; then
  echo 'Usage: sudo bash scripts/bootstrap-debian.sh --target-new-distro' >&2
  exit 2
fi
[[ $EUID == 0 ]] || { echo 'Run with sudo on the target only.' >&2; exit 1; }
source /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 && $(uname -m) == x86_64 ]] || exit 1
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confold upgrade
apt-get install -y ansible sudo python3-apt python3-venv ca-certificates rsync age zsh systemd-sysv
python3 - <<'PY'
import configparser
from pathlib import Path
p = Path('/etc/wsl.conf')
c = configparser.ConfigParser()
if p.exists():
    c.read(p)
if not c.has_section('boot'):
    c.add_section('boot')
c.set('boot', 'systemd', 'true')
c.remove_option('boot', 'command')
with p.open('w') as f:
    c.write(f)
PY
install -d -m 0755 /var/lib/wsl2-workstation
touch /var/lib/wsl2-workstation/bootstrap-ready
echo 'Restart THIS target distro from PowerShell, then run ansible-playbook -i inventory/hosts.yml site.yml -e @inventory/local.yml as root (or with -K from a sudo user).'
