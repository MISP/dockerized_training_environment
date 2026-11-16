#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''On all the instances, set the nationality of the organisations listed in org_nationalities (generic_config.py),
and use the matching country flag as organisation logo.

* MISP shows a flag next to the nationality (organisation index and view) only when the nationality is
  exactly the name of a country of the MISP country galaxy (e.g. 'Czechia', 'United States of America').
  'Europe' and 'International' are accepted but have no flag.
* The logo is shown next to the organisation name everywhere (events, sharing groups...). MISP looks for
  app/files/img/orgs/<org id|name|uuid>.<png|svg>: the flag SVGs shipped with MISP (app/webroot/img/flags)
  are copied there as <uuid>.svg, inside the misp-core containers.'''

import argparse
import json
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from subprocess import run

from pymisp import PyMISP, MISPOrganisation

import generic_config
from generic_config import central_node_name, secure_connection

org_nationalities: dict[str, str] = getattr(generic_config, 'org_nationalities', None) or {}

COUNTRY_GALAXY = '/var/www/MISP/app/files/misp-galaxy/clusters/country.json'
FLAGS_DIR = '/var/www/MISP/app/webroot/img/flags'
LOGOS_DIR = '/var/www/MISP/app/files/img/orgs'
# Nationalities accepted by MISP that are not in the country galaxy, but have a flag
EXTRA_FLAG_CODES = {'Europe': 'EU'}


def misp_core_container(instance_dir: Path) -> str:
    p = run(['sudo', 'docker', 'compose', 'ps', '-q', 'misp-core'], cwd=instance_dir, capture_output=True, text=True)
    return p.stdout.strip()


def country_codes(instance_dir: Path) -> dict[str, str]:
    '''Nationality (country name, as in MISP) -> ISO 3166-1 alpha-2 code, from the galaxy of a running instance'''
    container = misp_core_container(instance_dir)
    p = run(['sudo', 'docker', 'exec', container, 'cat', COUNTRY_GALAXY], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f'Unable to read the country galaxy from {instance_dir}: {p.stderr.strip()}')
    codes = {c['description']: c['meta']['ISO'] for c in json.loads(p.stdout)['values'] if c.get('meta', {}).get('ISO')}
    return {**codes, **EXTRA_FLAG_CODES}


def flag_file(country_code: str) -> str:
    '''Same naming as MISP's IconHelper::countryFlag: regional indicator code points, e.g. LU -> 1f1f1-1f1fa.svg'''
    return '-'.join(f'{0x1f1e6 + ord(letter) - ord("a"):x}' for letter in country_code.lower()) + '.svg'


def update_instance(instance_dir: Path, codes: dict[str, str], logos: bool, verify_ssl: bool, dry_run: bool) -> list[str]:
    with (instance_dir / 'config.json').open() as f:
        config = json.load(f)
    lines = [f"== {config['baseurl']}"]
    try:
        misp = PyMISP(config['baseurl'], config['admin_key'], ssl=verify_ssl, timeout=60)
        organisations = misp.organisations(scope='all', pythonify=True)
    except Exception as e:
        return lines + [f'   ERROR: unable to connect: {e}']
    if not isinstance(organisations, list):
        return lines + [f'   ERROR: unable to list the organisations: {organisations}']

    updated, unchanged, to_copy = [], 0, []
    for org in organisations:
        if not isinstance(org, MISPOrganisation) or org.name not in org_nationalities:
            continue
        nationality = org_nationalities[org.name]
        if getattr(org, 'nationality', None) == nationality:
            unchanged += 1
        elif dry_run:
            updated.append(org.name)
        else:
            org.nationality = nationality
            r = misp.update_organisation(org, org.id)
            if isinstance(r, dict) and r.get('errors'):
                lines.append(f'   ERROR updating {org.name}: {r["errors"]}')
            else:
                updated.append(org.name)
        if nationality in codes:
            to_copy.append((f'{FLAGS_DIR}/{flag_file(codes[nationality])}', f'{LOGOS_DIR}/{org.uuid}.svg'))
    lines.append(f'   nationality {"to set" if dry_run else "set"} on {len(updated)}, already correct on {unchanged}')

    if logos and to_copy:
        if dry_run:
            lines.append(f'   would copy {len(to_copy)} flags as logos')
        else:
            container = misp_core_container(instance_dir)
            script = ' && '.join([f'mkdir -p {LOGOS_DIR}',
                                  *(f'cp -f {shlex.quote(src)} {shlex.quote(dst)}' for src, dst in to_copy)])
            p = run(['sudo', 'docker', 'exec', '-u', 'www-data', container, 'sh', '-c', script], capture_output=True, text=True)
            if p.returncode == 0:
                lines.append(f'   {len(to_copy)} flags copied as logos')
            else:
                lines.append(f'   ERROR copying the flags as logos: {p.stderr.strip()}')
    return lines


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--no-logos', action='store_true', help='Only set the nationalities, do not touch the logos.')
    parser.add_argument('--dry-run', action='store_true', help='Only show what would be done.')
    parser.add_argument('-k', '--insecure', action='store_true',
                        help='Do not verify the TLS certificates (default: secure_connection from generic_config.py).')
    parser.add_argument('--root', default='misps', type=Path, help='Directory containing the instances (default: misps).')
    parser.add_argument('--workers', default=8, type=int, help='Number of instances processed in parallel (default: 8).')
    args = parser.parse_args()

    if not org_nationalities:
        parser.error('org_nationalities is empty in generic_config.py, nothing to do.')
    codes = country_codes(args.root / central_node_name)
    no_flag = sorted({n for n in org_nationalities.values() if n not in codes})
    if no_flag:
        print('No flag for these nationalities (not a country of the MISP galaxy, check the spelling):', ', '.join(no_flag))

    instance_dirs = sorted(p.parent for p in args.root.glob('*/config.json'))
    verify_ssl = False if args.insecure else secure_connection
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for lines in executor.map(lambda d: update_instance(d, codes, not args.no_logos, verify_ssl, args.dry_run), instance_dirs):
            print('\n'.join(lines))
