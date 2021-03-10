#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
from pymisp import PyMISP
import json
import argparse


def main():
    parser = argparse.ArgumentParser(description='Reset a user password')
    parser.add_argument('-i', '--instance', required=True)
    parser.add_argument('-u', '--user', required=True)
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
        print(f'unable to find user {args.user} in {args.instance}')


if __name__ == '__main__':
    main()
