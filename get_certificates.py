#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import shutil

certs_dir = Path('certs')
certs_dir.mkdir(exist_ok=True)

# Get wildcard cert
shutil.copytree('/etc/letsencrypt/live/berylia.org', certs_dir / 'berylia.org', dirs_exist_ok=True)
