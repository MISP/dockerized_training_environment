#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from pymisp import ExpandedPyMISP, MISPOrganisation, MISPUser
from generic_config import central_node_name, prefix_client_node

misp_instances_dir = Path('misps')


class MISPInstance():

    def __init__(self, node_id):
        with (misp_instances_dir / node_id / 'config.json').open() as f:
            self.instance_config = json.load(f)

        print('Initialize', self.instance_config['admin_orgname'])

        self.initial_user_connector = ExpandedPyMISP(self.instance_config['baseurl'], self.instance_config['admin_key'], ssl=False, debug=False)
        # Set the default role (id 3 is normal user)
        self.initial_user_connector.set_default_role(3)
        self.initial_user_connector.toggle_global_pythonify()

        # Create organisation
        organisation = MISPOrganisation()
        organisation.name = self.instance_config['admin_orgname']
        self.host_org = self.initial_user_connector.add_organisation(organisation)
        # Create Site admin in new org
        user = MISPUser()
        user.email = self.instance_config['email_site_admin']
        user.org_id = self.host_org.id
        user.role_id = 1  # Site admin
        self.host_site_admin = self.initial_user_connector.add_user(user)
        self.site_admin_connector = ExpandedPyMISP(self.instance_config['baseurl'], self.host_site_admin.authkey, ssl=False, debug=False)
        self.site_admin_connector.toggle_global_pythonify()

        # Setup external_baseurl
        self.site_admin_connector.set_server_setting('MISP.external_baseurl', self.instance_config['external_baseurl'], force=True)
        # Setup baseurl
        self.site_admin_connector.set_server_setting('MISP.baseurl', self.instance_config['baseurl'], force=True)
        # Setup host org
        self.site_admin_connector.set_server_setting('MISP.host_org_id', self.host_org.id)

        self.baseurl = self.instance_config['baseurl']
        self.external_baseurl = self.instance_config['external_baseurl']

    def __repr__(self):
        return f'<{self.__class__.__name__}(external={self.baseurl})>'

    def create_sync_user(self, organisation):
        sync_org = self.site_admin_connector.add_organisation(organisation)
        short_org_name = sync_org.name.lower().replace(' ', '-')
        user = MISPUser()
        user.email = f"sync_user@{short_org_name}.local"
        user.org_id = sync_org.id
        user.role_id = 5  # Org admin
        sync_user = self.site_admin_connector.add_user(user)
        sync_user_connector = ExpandedPyMISP(self.site_admin_connector.root_url, sync_user.authkey, ssl=False, debug=False)
        return sync_user_connector.get_sync_config(pythonify=True)

    def create_sync_server(self, name, server):
        server = self.site_admin_connector.import_server(server)
        server.self_signed = True
        server.pull = True  # Not automatic, but allows to do a pull
        server = self.site_admin_connector.update_server(server)
        r = self.site_admin_connector.test_server(server)
        if r['status'] != 1:
            raise Exception(f'Sync test failed: {r}')


central_node = MISPInstance(central_node_name)

for path in misp_instances_dir.glob(f'{prefix_client_node}*'):
    if path.name == central_node_name:
        continue
    instance = MISPInstance(path.name)
    sync_server_config = central_node.create_sync_user(instance.host_org)
    instance.create_sync_server(f'Sync with {sync_server_config.url}', sync_server_config)
