#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from misp_instances import MISPInstances

instances = MISPInstances()
instances.sync_push_all()
