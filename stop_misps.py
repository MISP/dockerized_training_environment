#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
from pathlib import Path
import shlex
from subprocess import Popen

from generic_config import (central_node_name, prefix_client_node)

parser = argparse.ArgumentParser(description='Stop all the MISP instances.')
parser.add_argument('--reset', action='store_true',
                    help='Also remove the containers and their volumes (database, events, users, sync config). '
                         'This cannot be undone.')
args = parser.parse_args()

root_misps = Path('misps')
command = shlex.split('sudo docker compose down -v' if args.reset else 'sudo docker compose stop')

# Stop all the instances
for path in [root_misps / central_node_name, *root_misps.glob(f'{prefix_client_node}*')]:
    p = Popen(command, cwd=path)
    p.wait()
