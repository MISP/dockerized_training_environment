#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from misp_instances import MISPInstances


if __name__ == '__main__':
    instances = MISPInstances()
    instances.setup_instances()
    # Mesh sync
    # instances.setup_sync_all()
    # Central only sync
    instances.setup_sync_central_only()
