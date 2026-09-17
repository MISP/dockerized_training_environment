#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from subprocess import check_call
import shlex
from pathlib import Path
from generic_config import prefix_client_node

misps_root = Path('misps')

for misp_dir in misps_root.glob(f'{prefix_client_node}*'):
    cur_dir = os.getcwd()
    os.chdir(misp_dir)
    command = shlex.split('sudo docker compose exec misp-core apt update')
    check_call(command)
    command = shlex.split('sudo docker compose exec misp-core apt install -y jq curl dialog')
    check_call(command)
    command = shlex.split('sudo docker compose exec misp-core bash /var/www/MISP/misp-refresh/refresh.sh -ni')
    check_call(command)
    os.chdir(cur_dir)
