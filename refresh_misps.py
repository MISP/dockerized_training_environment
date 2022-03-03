#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from subprocess import Popen
import shlex
from pathlib import Path
from generic_config import prefix_client_node

misps_root = Path('misps')

for misp_dir in misps_root.glob(f'{prefix_client_node}*'):
    cur_dir = os.getcwd()
    os.chdir(misp_dir)
    command = shlex.split('sudo docker-compose exec misp apt update')
    p = Popen(command)
    p.wait()
    command = shlex.split('sudo docker-compose exec misp apt install -y jq curl dialog')
    p = Popen(command)
    p.wait()
    command = shlex.split('sudo docker-compose exec misp bash /var/www/MISP/misp-refresh/refresh.sh -ni')
    p = Popen(command)
    p.wait()
    os.chdir(cur_dir)
