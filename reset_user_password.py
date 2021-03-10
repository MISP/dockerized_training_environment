#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
from pymisp import PyMISP, MISPUser
import json
import argparse


def create_user(connector, config, email):
    organisations = connector.organisations(pythonify=True)
    for organisation in organisations:
        if organisation.name == config['admin_orgname']:
            host_org = organisation
            break
    else:
        raise Exception('No default org found.')
    user = MISPUser()
    user.email = email
    user.org_id = host_org.id
    user.role_id = 1
    user.password = 'Password1234'
    new_user = connector.add_user(user)
    print(new_user)


def main():
    parser = argparse.ArgumentParser(description='Reset a user password / create a user')
    parser.add_argument('-i', '--instance', required=True)
    parser.add_argument('-u', '--user', required=True)
    parser.add_argument('--create_if_missing', default=False, action='store_true')
    args = parser.parse_args()

    with (Path('misps') / args.instance / 'config.json').open() as f:
        config = json.load(f)

    initial_user_connector = PyMISP(config['baseurl'], config['admin_key'], ssl=False, debug=False)
    for user in initial_user_connector.users(pythonify=True):
        if user.email == args.user:
            u = initial_user_connector.update_user({'password': 'Password1234'}, user.id)
            print(u)
            break
    else:
        if args.create_if_missing:
            create_user(initial_user_connector, config, args.user)
        else:
            print(f'unable to find user {args.user} in {args.instance}')


if __name__ == '__main__':
    main()
