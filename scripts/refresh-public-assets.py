#!/usr/bin/env python3
"""Maintainer command: download explicit upstream revisions and freeze SHA256s."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

SOURCES = [
    {'name': 'oh-my-zsh', 'revision': 'b509b1c6ed0c1ba37de12cbd37f30b2b2f61193a',
     'url': 'https://codeload.github.com/ohmyzsh/ohmyzsh/tar.gz/b509b1c6ed0c1ba37de12cbd37f30b2b2f61193a',
     'destination': '.oh-my-zsh', 'module': 'shell'},
    {'name': 'uv', 'revision': '0.9.28',
     'url': 'https://github.com/astral-sh/uv/releases/download/0.9.28/uv-x86_64-unknown-linux-gnu.tar.gz',
     'destination': '.local/bin', 'module': 'uv'},
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write-lock', action='store_true', required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    directory = root / 'artifacts/public-assets'
    directory.mkdir(parents=True, exist_ok=True)
    result = []
    for entry in SOURCES:
        archive = directory / (entry['name'] + '.tar.gz')
        h = hashlib.sha256()
        with urllib.request.urlopen(entry['url'], timeout=45) as r, archive.open('wb') as f:
            while block := r.read(1024 * 1024):
                h.update(block)
                f.write(block)
        result.append({**entry, 'sha256': h.hexdigest()})
    (root / 'manifests/public-assets.json').write_text(json.dumps({'schema': 1, 'assets': result}, indent=2) + '\n')
    print('Public asset lock generated from fixed upstream revisions. Review the diff before committing.')


if __name__ == '__main__':
    main()
