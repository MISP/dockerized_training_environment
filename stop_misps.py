#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import os
import shlex
from subprocess import Popen

from generic_config import (central_node_name, prefix_client_node)

root_misps = Path('misps')

# Start all the instances
cur_dir = os.getcwd()
os.chdir(root_misps / central_node_name)
command = shlex.split('sudo docker compose stop')
p = Popen(command)
p.wait()
os.chdir(cur_dir)
for path in root_misps.glob(f'{prefix_client_node}*'):
    cur_dir = os.getcwd()
    os.chdir(path)
    command = shlex.split('sudo docker compose stop')
    p = Popen(command)
    p.wait()
    os.chdir(cur_dir)
