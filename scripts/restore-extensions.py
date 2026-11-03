#!/usr/bin/env python3
"""Install extension IDs captured by collect.py; run separately on Windows/WSL."""
import argparse
import json
import re
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('inventory', type=Path)
p.add_argument('--surface', choices=['wsl', 'windows'], required=True)
p.add_argument('--code', default='code', help='WSL: Remote-WSL code CLI; Windows: code.cmd')
p.add_argument('--apply', action='store_true')
a = p.parse_args()
ids = json.loads(a.inventory.read_text())[f'vscode_{a.surface}_extensions']
for extension in ids:
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_.-]+', extension):
        p.error('Invalid extension ID in inventory')
    if a.apply:
        subprocess.run([a.code, '--install-extension', extension], check=True)
    else:
        print(f'{a.surface}: {extension}')
