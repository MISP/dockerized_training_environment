#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
from pymisp import PyMISP

from generic_config import (central_node_name, prefix_client_node, secure_connection)


class SyncAll():

    central_node_name = central_node_name
    prefix_client_node = prefix_client_node
    secure_connection = secure_connection

    def __init__(self, root_misps: str='misps'):
        self.misp_instances_dir = Path(__file__).resolve().parent / root_misps

        central_node_config_path = self.misp_instances_dir / self.central_node_name
        with (central_node_config_path / 'config.json').open() as f:
            config_central_node = json.load(f)

        self.central_node = PyMISP(config_central_node['baseurl'], config_central_node['admin_key'],
                                   ssl=self.secure_connection, debug=False)

        self.clients = []
        for path in self.misp_instances_dir.glob(f'{self.prefix_client_node}*'):
            if path.name == self.central_node_name:
                continue
            with (path / 'config.json').open() as f:
                config = json.load(f)
            client = PyMISP(config['baseurl'], config['admin_key'], ssl=self.secure_connection,
                            debug=False)
            self.clients.append(client)

    def _sync_all(self, node: PyMISP):
        for server in node.servers(pythonify=True):
            node.server_push(server)

    def trigger_sync(self):
        self._sync_all(self.central_node)
        for client in self.clients:
            self._sync_all(client)


if __name__ == '__main__':
    sync = SyncAll()
    sync.trigger_sync()
