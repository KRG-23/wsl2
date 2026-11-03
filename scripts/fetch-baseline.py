#!/usr/bin/env python3
"""Verify official WSL image and read package metadata without booting/extracting it."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request


def parse_status(text):
    result = {}
    for paragraph in text.split('\n\n'):
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line and not line.startswith(' '))
        if fields.get('Status') != 'install ok installed':
            continue
        name = fields['Package']
        if fields.get('Multi-Arch') == 'same' and fields.get('Architecture') != 'all':
            name += ':' + fields['Architecture']
        result[name] = fields['Version']
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, default=Path('artifacts/baseline'))
    a = p.parse_args()
    lock = json.loads((Path(__file__).resolve().parents[1] / 'manifests/debian-image.json').read_text())
    a.directory.mkdir(parents=True, exist_ok=True)
    image = a.directory / 'debian-amd64.wsl'
    partial = image.with_suffix('.partial')
    if not image.exists():
        h = hashlib.sha256()
        try:
            with urllib.request.urlopen(lock['url'], timeout=60) as response, partial.open('xb') as f:
                while block := response.read(1024 * 1024):
                    f.write(block)
                    h.update(block)
            if h.hexdigest() != lock['sha256']:
                raise ValueError('Official image SHA256 mismatch')
            partial.rename(image)
        finally:
            if partial.exists():
                partial.unlink()
    with image.open('rb') as f:
        h = hashlib.file_digest(f, 'sha256').hexdigest()
    if h != lock['sha256']:
        raise ValueError('Cached image SHA256 mismatch')
    metadata = {}
    with tarfile.open(image, 'r:*') as tar:
        for member in tar:
            name = member.name.removeprefix('./')
            if name in {'var/lib/dpkg/status', 'etc/os-release', 'usr/lib/os-release'} and member.isfile():
                metadata[name] = tar.extractfile(member).read().decode()
    release = metadata.get('etc/os-release', metadata.get('usr/lib/os-release', ''))
    if 'VERSION_ID="13"' not in release and 'VERSION_ID=13\n' not in release:
        raise ValueError('Image is not Debian 13; explicitly update the image lock before proceeding')
    packages = parse_status(metadata['var/lib/dpkg/status'])
    result = {'schema': 1, 'package_inventory_ok': True, 'packages': packages, 'image': lock,
              'os_release_raw': release, 'baseline_kind': 'official WSL rootfs before first boot; not upgraded'}
    (a.directory / 'inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'Verified official WSL image: {len(packages)} packages; {a.directory}/inventory.json')


if __name__ == '__main__':
    main()
