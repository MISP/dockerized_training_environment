#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from subprocess import Popen
import shlex
from pathlib import Path

misps_root = Path('misps')

for misp_dir in misps_root.glob('misp*'):
    cur_dir = os.getcwd()
    os.chdir(misp_dir)
    command = shlex.split('sudo docker-compose exec misp apt update')
    p = Popen(command)
    p.wait()
    command = shlex.split('sudo docker-compose exec misp apt install -y jq curl dialog')
    p = Popen(command)
    p.wait()
    command = shlex.split('sudo docker-compose exec misp bash /var/www/MISP/misp-refresh/refresh.sh')
    p = Popen(command)
    p.wait()
    os.chdir(cur_dir)
