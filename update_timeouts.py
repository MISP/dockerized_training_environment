#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from misp_instances import MISPInstances

if __name__ == '__main__':
    instances = MISPInstances()
    instances.central_node.change_session_timeout(300)
    for node in instances.client_nodes.values():
        node.change_session_timeout(300)
