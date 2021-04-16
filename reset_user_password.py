#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse

from misp_instances import MISPInstances
from generic_config import (central_node_name)


def main():
    parser = argparse.ArgumentParser(description='Reset a user password / create a user.')
    parser.add_argument('-u', '--user', required=True, help='Email address of the user, login name')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--instance', required=False, help='Name of the admin org on the instance. Quote if there is a space (ex. "MISP 01")')
    group.add_argument('--everywhere', default=False, action='store_true', help='Create/update and all the instances')
    args = parser.parse_args()

    instances = MISPInstances()

    if args.instance:
        if args.instance == central_node_name:
            instances.central_node.init_default_user(args.email)
        elif args.instance in instances.client_nodes:
            instances.client_nodes[args.instance].init_default_user(args.email)
        else:
            available = list(instances.client_nodes.keys())
            raise Exception(f'Available instances: {available}')
    else:
        instances.central_node.init_default_user(args.email)
        for node in instances.client_nodes.values():
            node.init_default_user(args.email)


if __name__ == '__main__':
    main()
