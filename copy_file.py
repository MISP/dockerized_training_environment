#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from misp_instances import MISPInstances

import argparse


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='copy a file or a directory to all the instances')
    parser.add_argument('-s', '--source', required=True)
    parser.add_argument('-d', '--destination', required=True)
    args = parser.parse_args()

    instances = MISPInstances()
    instances.central_node.copy_file(args.source, args.destination)
    for node in instances.client_nodes.values():
        node.copy_file(args.source, args.destination)
