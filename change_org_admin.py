#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

from pymisp import PyMISP, MISPUser

from generic_config import (central_node_name, prefix_client_node, secure_connection)


def create_or_update_user(connector: PyMISP, user: MISPUser) -> MISPUser:
    to_return_user = connector.add_user(user)
    if isinstance(to_return_user, MISPUser):
        return to_return_user
    # The user already exists
    for u in connector.users():
        if u.email == user.email:
            to_return_user = connector.update_user(user, u.id)
            if isinstance(to_return_user, MISPUser):
                return to_return_user
            raise Exception(f'Unable to update {user.email}: {to_return_user}')
    else:
        raise Exception(f'Unable to create {user.email}: {to_return_user}')


class MISPInstances():

    central_node_name = central_node_name
    prefix_client_node = prefix_client_node
    secure_connection = secure_connection

    def __init__(self, root_misps: str='misps'):
        self.misp_instances_dir = Path(__file__).resolve().parent / root_misps
        self._connect_to_all_instances()

    def _connect_to_all_instances(self):
        with (self.misp_instances_dir / self.central_node_name / 'config.json').open() as f:
            config_central_node = json.load(f)
        self.connector_central_node = (PyMISP(config_central_node['baseurl'], config_central_node['admin_key'], ssl=self.secure_connection, debug=False), config_central_node)

        self.connectors_client_nodes = []
        for path in self.misp_instances_dir.glob(f'{self.prefix_client_node}*'):
            with (path / 'config.json').open() as f:
                instance_config = json.load(f)
            connector_node = PyMISP(instance_config['baseurl'], instance_config['admin_key'], ssl=self.secure_connection, debug=False)
            self.connectors_client_nodes.append((connector_node, instance_config))

    def change_admin_users_org(self, new_org_id):
        user = MISPUser()
        user.email = self.connector_central_node[1]['email_site_admin']
        user.org_id = new_org_id
        create_or_update_user(self.connector_central_node[0], user)
        for connector, config in self.connectors_client_nodes:
            user = MISPUser()
            user.email = config['email_site_admin']
            user.org_id = new_org_id
            create_or_update_user(connector, user)


if __name__ == '__main__':
    instances = MISPInstances()
    instances.change_admin_users_org(1)
