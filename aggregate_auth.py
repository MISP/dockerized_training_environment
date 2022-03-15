#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json

from misp_instances import MISPInstances


def auth_from_config(config):
    auth_admin = {'url': config['baseurl'], 'login': 'admin@admin.test', 'authkey': config['admin_key'], 'password': config['admin_password']}
    site_admin = {'url': config['baseurl'], 'login': config['email_site_admin'], 'authkey': config['site_admin_authkey'], 'password': 'N/A'}
    org_admin = {'url': config['baseurl'], 'login': config['email_orgadmin'], 'authkey': config['orgadmin_authkey'], 'password': 'N/A'}
    return auth_admin, site_admin, org_admin


if __name__ == '__main__':
    to_dump = []
    instances = MISPInstances()
    auth_admin, site_admin, org_admin = auth_from_config(instances.central_node.config)
    to_dump.append(auth_admin)
    to_dump.append(site_admin)
    to_dump.append(org_admin)
    for node in instances.client_nodes.values():
        auth_admin, site_admin, org_admin = auth_from_config(node.config)
        to_dump.append(auth_admin)
        to_dump.append(site_admin)
        to_dump.append(org_admin)

    with (instances.misp_instances_dir / 'auth.json').open('w') as f:
        json.dump(to_dump, f, indent=2)

    with (instances.misp_instances_dir / 'auth.csv').open('w') as csvfile:
        fieldnames = ['url', 'login', 'authkey', 'password']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for a in to_dump:
            writer.writerow(a)
