#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from subprocess import Popen
import shlex
from pathlib import Path

nginx_root = Path('nginx-proxy')
cur_dir = os.getcwd()
os.chdir(nginx_root)
command = shlex.split('sudo docker compose stop')
p = Popen(command)
p.wait()
os.chdir(cur_dir)
