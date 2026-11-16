#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''Delete, on all the instances, the sharing groups that are not in the keep list.
By default, only the sharing groups defined in additional_sharinggroups (generic_config.py) are kept,
which removes the 1-to-1 "Sharing group with <org>" groups created by setup_sync.py.
Without --apply, only shows what would be deleted.'''

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pymisp import PyMISP, MISPSharingGroup

from generic_config import additional_sharinggroups, secure_connection


def instance_configs(root: Path) -> list[dict]:
    configs = []
    for config_path in sorted(root.glob('*/config.json')):  # Only the instance roots, not misp-guard's config
        with config_path.open() as f:
            configs.append(json.load(f))
    return configs


def clean_instance(config: dict, keep: set[str], apply: bool, verify_ssl: bool) -> list[str]:
    lines = [f"== {config['baseurl']}"]
    try:
        misp = PyMISP(config['baseurl'], config['admin_key'], ssl=verify_ssl, timeout=60)
        sharing_groups = misp.sharing_groups(pythonify=True)
    except Exception as e:
        return lines + [f'   ERROR: unable to connect: {e}']
    if not isinstance(sharing_groups, list):
        return lines + [f'   ERROR: unable to list the sharing groups: {sharing_groups}']

    for sg in sharing_groups:
        if not isinstance(sg, MISPSharingGroup) or sg.name in keep:
            continue
        if not apply:
            lines.append(f'   would delete: {sg.name}')
            continue
        r = misp.delete_sharing_group(sg)
        if isinstance(r, dict) and r.get('errors'):
            lines.append(f'   ERROR deleting {sg.name}: {r["errors"]}')
        else:
            lines.append(f'   deleted: {sg.name}')
    kept = [sg.name for sg in sharing_groups if isinstance(sg, MISPSharingGroup) and sg.name in keep]
    lines.append(f'   kept {len(kept)}: {", ".join(kept) or "-"}')
    return lines


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='Really delete (default: only show what would be deleted).')
    parser.add_argument('--keep', action='append', default=[], metavar='NAME',
                        help='Also keep this sharing group (can be repeated).')
    parser.add_argument('--root', default='misps', type=Path, help='Directory containing the instances (default: misps).')
    parser.add_argument('-k', '--insecure', action='store_true',
                        help='Do not verify the TLS certificates (default: secure_connection from generic_config.py).')
    parser.add_argument('--workers', default=8, type=int, help='Number of instances processed in parallel (default: 8).')
    args = parser.parse_args()

    keep = set(additional_sharinggroups or {}) | set(args.keep)
    if not keep:
        parser.error('Nothing to keep: additional_sharinggroups is empty and no --keep given, refusing to delete everything.')
    verify_ssl = False if args.insecure else secure_connection
    configs = instance_configs(args.root)
    print(f'{len(configs)} instances. Keeping {len(keep)} sharing groups:', *sorted(keep), sep='\n  * ')
    if not args.apply:
        print('Dry run, nothing is deleted. Re-run with --apply to delete.')

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for lines in executor.map(lambda c: clean_instance(c, keep, args.apply, verify_ssl), configs):
            print('\n'.join(lines))
