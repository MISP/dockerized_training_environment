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
    command = shlex.split('sudo docker-compose stop')
    p = Popen(command)
    p.wait()
    os.chdir(cur_dir)
