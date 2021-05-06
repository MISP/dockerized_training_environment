#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from misp_instances import MISPInstances


if __name__ == '__main__':
    instances = MISPInstances()
    instances.dump_all_events()
