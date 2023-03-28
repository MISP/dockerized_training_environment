#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os

from datetime import datetime, timedelta
from pathlib import Path

from misp_instances import MISPInstances

lock_file = Path('/tmp/trigger_sync.pid')


def try_make_file(filename: Path):
    try:
        filename.touch(exist_ok=False)
        return True
    except FileExistsError:
        return False


def is_locked(lock_file: Path, /, *, expire_in_min: int=30) -> bool:
    """Check if a capture directory is locked, if the lock is recent enough,
    and if the locking process is still running.

    :param locked_dir_path: Path of the directory.
    """
    if not lock_file.exists():
        # No lock file
        return False

    try:
        with lock_file.open('r') as f:
            content = f.read()
            ts, pid = content.split(';')
            try:
                os.kill(int(pid), 0)
            except OSError:
                logging.info(f'Lock by dead script {lock_file}, removing it.')
                lock_file.unlink(missing_ok=True)
                return False

        lock_ts = datetime.fromisoformat(ts)
        if lock_ts < datetime.now() - timedelta(minutes=expire_in_min):
            # Clear old locks. They shouldn't be there, but it's gonna happen.
            logging.info(f'Old lock ({lock_ts.isoformat()}) {lock_file}, removing it.')
            lock_file.unlink(missing_ok=True)
            return False
    except Exception:
        logging.exception('Lock found, but unable to process.')
        return True

    # The lockfile is here for a good reason.
    return True


if not is_locked(lock_file) and try_make_file(lock_file):
    with lock_file.open('w') as f:
        f.write(f"{datetime.now().isoformat()};{os.getpid()}")

    instances = MISPInstances()
    instances.sync_push_all()
