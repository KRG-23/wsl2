#!/usr/bin/env python3
"""Compare two inventories without guessing a fresh Debian baseline."""
import argparse
import json
from pathlib import Path


def compare(baseline, current):
    for data in [baseline, current]:
        if data.get('schema') != 1 or not data.get('package_inventory_ok'):
            raise ValueError('A complete schema 1 package inventory is required.')
    b, c = baseline['packages'], current['packages']
    return {'added_packages': {k: c[k] for k in sorted(c.keys() - b.keys())},
            'removed_packages': {k: b[k] for k in sorted(b.keys() - c.keys())},
            'changed_versions': {k: {'baseline': b[k], 'current': c[k]} for k in sorted(b.keys() & c.keys()) if b[k] != c[k]},
            'extensions_added': {key: sorted(set(current.get(key, [])) - set(baseline.get(key, [])))
                                 for key in ['vscode_wsl_extensions', 'vscode_windows_extensions']},
            'note': 'Added packages include dependencies. Version changes alone do not prove customization.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline', type=Path)
    p.add_argument('current', type=Path)
    a = p.parse_args()
    print(json.dumps(compare(json.loads(a.baseline.read_text()), json.loads(a.current.read_text())), indent=2))


if __name__ == '__main__':
    main()
