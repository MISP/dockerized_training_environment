#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from pymisp import ExpandedPyMISP, MISPOrganisation, MISPUser, MISPSharingGroup
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

        self.baseurl = self.instance_config['baseurl']
        self.external_baseurl = self.instance_config['external_baseurl']

        # Create organisation
        organisation = MISPOrganisation()
        organisation.name = self.instance_config['admin_orgname']
        self.host_org = self.initial_user_connector.add_organisation(organisation)
        if not isinstance(self.host_org, MISPOrganisation):
            # The organisation is probably already there
            organisations = self.initial_user_connector.organisations()
            for organisation in organisations:
                if organisation.name == self.instance_config['admin_orgname']:
                    self.host_org = organisation
                    break
            else:
                raise Exception('Unable to find admin organisation')

        # Create Site admin in new org
        user = MISPUser()
        user.email = self.instance_config['email_site_admin']
        user.org_id = self.host_org.id
        user.role_id = 1  # Site admin
        self.host_site_admin = self.initial_user_connector.add_user(user)
        if not isinstance(self.host_site_admin, MISPUser):
            users = self.initial_user_connector.users()
            for user in users:
                if user.email == self.instance_config['email_site_admin']:
                    self.host_site_admin = user
                    break
            else:
                raise Exception('Unable to find admin user')

        self.site_admin_connector = ExpandedPyMISP(self.baseurl, self.host_site_admin.authkey, ssl=False, debug=False)
        self.site_admin_connector.toggle_global_pythonify()

        # Setup external_baseurl
        self.site_admin_connector.set_server_setting('MISP.external_baseurl', self.external_baseurl, force=True)
        # Setup baseurl
        self.site_admin_connector.set_server_setting('MISP.baseurl', self.baseurl, force=True)
        # Setup host org
        self.site_admin_connector.set_server_setting('MISP.host_org_id', self.host_org.id)

    def __repr__(self):
        return f'<{self.__class__.__name__}(external={self.baseurl})>'

    def create_sync_user(self, organisation):
        sync_org = self.site_admin_connector.add_organisation(organisation)
        if not isinstance(sync_org, MISPOrganisation):
            # The organisation is probably already there
            organisations = self.initial_user_connector.organisations()
            for org in organisations:
                if org.name == organisation.name:
                    sync_org = org
                    break
            else:
                raise Exception('Unable to find sync organisation')

        short_org_name = sync_org.name.lower().replace(' ', '-')
        email = f"sync_user@{short_org_name}.local"
        user = MISPUser()
        user.email = email
        user.org_id = sync_org.id
        user.role_id = 5  # Sync user
        sync_user = self.site_admin_connector.add_user(user)
        if not isinstance(sync_user, MISPUser):
            users = self.initial_user_connector.users()
            for user in users:
                if user.email == email:
                    sync_user = user
                    break
            else:
                raise Exception('Unable to find sync user')

        sync_user_connector = ExpandedPyMISP(self.site_admin_connector.root_url, sync_user.authkey, ssl=False, debug=False)
        return sync_user_connector.get_sync_config(pythonify=True)

    def create_sync_server(self, server_sync_config):
        for s in self.site_admin_connector.servers():
            if s.name == server_sync_config.name:
                server = s
                break
        else:
            server = self.site_admin_connector.import_server(server_sync_config)
        server.self_signed = True
        server.pull = True  # Not automatic, but allows to do a pull
        server = self.site_admin_connector.update_server(server)
        r = self.site_admin_connector.test_server(server)
        if r['status'] != 1:
            raise Exception(f'Sync test failed: {r}')

        for sg in self.site_admin_connector.sharing_groups():
            if sg.name == 'Sharing group with central node':
                sharing_group = sg
                break
        else:
            sharing_group = MISPSharingGroup()
            sharing_group.name = 'Sharing group with central node'
            sharing_group.releasability = 'Training'
            sharing_group = self.site_admin_connector.add_sharing_group(sharing_group)
            self.site_admin_connector.add_server_to_sharing_group(sharing_group, server)
            self.site_admin_connector.add_org_to_sharing_group(sharing_group, server_sync_config.Organisation)


central_node = MISPInstance(central_node_name)

for path in misp_instances_dir.glob(f'{prefix_client_node}*'):
    if path.name == central_node_name:
        continue
    instance = MISPInstance(path.name)
    sync_server_config = central_node.create_sync_user(instance.host_org)
    sync_server_config.name = f'Sync with {sync_server_config.url}'
    instance.create_sync_server(sync_server_config)
