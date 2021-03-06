#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from pymisp import PyMISP, MISPOrganisation, MISPUser, MISPSharingGroup, MISPTag, MISPEvent
import random
import string
import csv

from generic_config import central_node_name, prefix_client_node, secure_connection


class MISPInstance():

    def __init__(self, misp_instance_dir, secure_connection):
        with (misp_instance_dir / 'config.json').open() as f:
            self.instance_config = json.load(f)

        print('Initialize', self.instance_config['admin_orgname'])
        self.secure_connection = secure_connection

        self.initial_user_connector = PyMISP(self.instance_config['baseurl'], self.instance_config['admin_key'], ssl=self.secure_connection, debug=False)
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

        self.site_admin_connector = PyMISP(self.baseurl, self.host_site_admin.authkey, ssl=self.secure_connection, debug=False)
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

        sync_user_connector = PyMISP(self.site_admin_connector.root_url, sync_user.authkey, ssl=self.secure_connection, debug=False)
        return sync_user_connector.get_sync_config(pythonify=True)

    def configure_sync(self, server_sync_config):
        # Add sharing server
        for s in self.site_admin_connector.servers():
            if s.name == server_sync_config.name:
                server = s
                break
        else:
            server = self.site_admin_connector.import_server(server_sync_config)
        server.pull = False
        server.push = True  # Not automatic, but allows to do a push
        server = self.site_admin_connector.update_server(server)
        r = self.site_admin_connector.test_server(server)
        if r['status'] != 1:
            raise Exception(f'Sync test failed: {r}')

        # Add tag to limit push
        tag = MISPTag()
        tag.name = 'push_to_central'
        tag.exportable = False
        tag.org_id = self.host_org.id
        tag = self.site_admin_connector.add_tag(tag)
        if not isinstance(tag, MISPTag):
            for t in self.site_admin_connector.tags():
                if t.name == 'push_to_central':
                    tag = t
                    break
            else:
                raise Exception('Unable to find tag')

        # Set limit on sync config
        filter_tag_push = {"tags": {'OR': [tag.id], 'NOT': []}, 'orgs': {'OR': [], 'NOT': []}}
        # filter_tag_pull = {"tags": {'OR': [], 'NOT': []}, 'orgs': {'OR': [], 'NOT': []}}
        server.push_rules = json.dumps(filter_tag_push)
        # server.pull_rules = json.dumps(filter_tag_pull)
        server = self.site_admin_connector.update_server(server)

        # Add sharing group
        for sg in self.site_admin_connector.sharing_groups():
            if sg.name == 'Sharing group with central node':
                self.sharing_group = sg
                break
        else:
            sharing_group = MISPSharingGroup()
            sharing_group.name = 'Sharing group with central node'
            sharing_group.releasability = 'Training'
            self.sharing_group = self.site_admin_connector.add_sharing_group(sharing_group)
            self.site_admin_connector.add_server_to_sharing_group(self.sharing_group, server)
            self.site_admin_connector.add_org_to_sharing_group(self.sharing_group, server_sync_config.Organisation)

    def create_org_admin(self):
        # Create org admin (will be used during the exercise)
        user = MISPUser()
        user.email = self.instance_config['email_orgadmin']
        user.org_id = self.host_org.id
        user.role_id = 2  # Org admin
        self.org_admin = self.initial_user_connector.add_user(user)
        if not isinstance(self.org_admin, MISPUser):
            users = self.initial_user_connector.users()
            for user in users:
                if user.email == self.instance_config['email_orgadmin']:
                    self.org_admin = user
                    break
            else:
                raise Exception('Unable to find org admin')


class MISPInstances():

    central_node_name = central_node_name
    prefix_client_node = prefix_client_node
    secure_connection = secure_connection

    def __init__(self, root_misps: str='misps'):
        self.misp_instances_dir = Path(root_misps)

        self.central_node = MISPInstance(self.misp_instances_dir / self.central_node_name, self.secure_connection)
        self.central_node.create_org_admin()

        self.instances = []

        # Initialize all instances to sync with central node
        for path in self.misp_instances_dir.glob(f'{self.prefix_client_node}*'):
            if path.name == self.central_node_name:
                continue
            instance = MISPInstance(path, self.secure_connection)
            sync_server_config = self.central_node.create_sync_user(instance.host_org)
            sync_server_config.name = f'Sync with {sync_server_config.url}'
            instance.configure_sync(sync_server_config)
            instance.create_org_admin()
            self.instances.append(instance)

    def test_sync(self, instance_id: int=0):
        event = MISPEvent()
        event.info = 'test sync'
        event.add_tag('push_to_central')
        event.add_attribute('ip-src', '8.8.8.8')
        event.distribution = 4
        event.SharingGroup = self.instances[instance_id].sharing_group

        self.instances[instance_id].site_admin_connector.add_event(event)
        self.instances[instance_id].site_admin_connector.publish(event)

    def dump_all_auth(self):
        auth = []
        for instance in self.instances + [self.central_node]:
            for user in instance.site_admin_connector.users():
                if user.change_pw == '1':
                    # Only change the password if the user never logged in.
                    password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                    instance.site_admin_connector.change_user_password(password, user)
                else:
                    password = 'Already changed by the user'
                a = {'url': instance.baseurl, 'login': user.email, 'authkey': user.authkey,
                     'password': password}
                auth.append(a)

        with (self.misp_instances_dir / 'auth.json').open('w') as f:
            json.dump(auth, f, indent=2)

        with (self.misp_instances_dir / 'auth.csv').open('w') as csvfile:
            fieldnames = ['url', 'login', 'authkey', 'password']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for a in auth:
                writer.writerow(a)


if __name__ == '__main__':
    instances = MISPInstances()
    instances.dump_all_auth()
    with (instances.misp_instances_dir / 'auth.json').open() as f:
        print(f.read())
    with (instances.misp_instances_dir / 'auth.csv').open() as f:
        print(f.read())
