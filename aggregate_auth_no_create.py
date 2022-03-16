#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
from pathlib import Path


def auth_from_config(config):
    auth_admin = {'url': config['baseurl'], 'login': 'admin@admin.test', 'authkey': config['admin_key'], 'password': config['admin_password']}
    site_admin = {'url': config['baseurl'], 'login': config['email_site_admin'], 'authkey': config.get('site_admin_authkey', 'n/a'), 'password': config.get('site_admin_password', 'n/a')}
    org_admin = {'url': config['baseurl'], 'login': config['email_orgadmin'], 'authkey': config.get('orgadmin_authkey', 'n/a'), 'password': config.get('orgadmin_password', 'n/a')}
    return auth_admin, site_admin, org_admin


if __name__ == '__main__':
    to_dump = []
    for cp in Path('misps').glob('**/config.json'):
        with cp.open() as f:
            config = json.load(f)
        auth_admin, site_admin, org_admin = auth_from_config(config)
        to_dump.append(auth_admin)
        to_dump.append(site_admin)
        to_dump.append(org_admin)

    with (Path('misps') / 'auth.json').open('w') as f:
        json.dump(to_dump, f, indent=2)

    with (Path('misps') / 'auth.csv').open('w') as csvfile:
        fieldnames = ['url', 'login', 'authkey', 'password']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for a in to_dump:
            writer.writerow(a)
