#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from pymisp import ExpandedPyMISP, MISPOrganisation, MISPUser

misp_instances_dir = Path('misps')

central_node_config = {
    'misp_central': {
        'orgname': 'Central Node',
        'email_site_admin': 'admin@centralnode.local'
    }
}

orgs_config = {
    'misp1': {
        'orgname': 'Node 1',
        'email_site_admin': 'admin@node1.local'
    },
    'misp2': {
        'orgname': 'Node 2',
        'email_site_admin': 'admin@node2.local'
    },
    'misp3': {
        'orgname': 'Node 3',
        'email_site_admin': 'admin@node3.local'
    },
    'misp4': {
        'orgname': 'Node 4',
        'email_site_admin': 'admin@node4.local'
    },
    'misp5': {
        'orgname': 'Node 5',
        'email_site_admin': 'admin@node5.local'
    }
}


class MISPInstance():

    def __init__(self, node_id, params):
        with (misp_instances_dir / node_id / 'config.json').open() as f:
            self.instance_config = json.load(f)

        self.initial_user_connector = ExpandedPyMISP(self.instance_config['baseurl'], self.instance_config['admin_key'], ssl=False, debug=False)
        # Set the default role (id 3 is normal user)
        self.initial_user_connector.set_default_role(3)
        self.initial_user_connector.toggle_global_pythonify()

        # Create organisation
        organisation = MISPOrganisation()
        organisation.name = params['orgname']
        self.host_org = self.initial_user_connector.add_organisation(organisation)
        # Create Site admin in new org
        user = MISPUser()
        user.email = params['email_site_admin']
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


central_node = MISPInstance('misp_central', central_node_config['misp_central'])

for node_id, params in orgs_config.items():
    instance = MISPInstance(node_id, params)
    sync_server_config = central_node.create_sync_user(instance.host_org)
    instance.create_sync_server(f'Sync with {sync_server_config.url}', sync_server_config)
