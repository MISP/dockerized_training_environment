#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import random
import shlex
import string

from subprocess import Popen, PIPE
from pathlib import Path
from typing import Optional

from pymisp import PyMISP, MISPUser, MISPTag, MISPOrganisation, MISPSharingGroup

from generic_config import (central_node_name, prefix_client_node, secure_connection,
                            internal_network_name, enabled_taxonomies, unpublish_on_sync,
                            tag_central_to_nodes, tag_nodes_to_central, local_tags_central,
                            reserved_tags_central, local_tags_clients)


def create_or_update_site_admin(connector: PyMISP, user: MISPUser) -> MISPUser:
    to_return_user = connector.add_user(user)
    if isinstance(to_return_user, MISPUser):
        return to_return_user
    # The user already exists
    for u in connector.users():
        if u.email == user.email:
            to_return_user = connector.update_user(user, u.id)  # type: ignore
            if isinstance(to_return_user, MISPUser):
                return to_return_user
            raise Exception(f'Unable to update {user.email}: {to_return_user}')
    else:
        raise Exception(f'Unable to create {user.email}: {to_return_user}')


class MISPInstance():
    owner_orgname: str
    site_admin: PyMISP
    _owner_site_admin: Optional[PyMISP] = None
    _owner_orgadmin: Optional[PyMISP] = None

    @property
    def host_org(self) -> MISPOrganisation:
        organisation = MISPOrganisation()
        organisation.name = self.config['admin_orgname']
        return self.create_or_update_organisation(organisation)

    @property
    def owner_site_admin(self) -> PyMISP:
        if self._owner_site_admin:
            return self._owner_site_admin
        for user in self.site_admin.users():
            if user.email == self.config['email_site_admin']:
                break
        else:
            # The user doesn't exists
            user = MISPUser()
            user.email = self.config['email_site_admin']
            user.org_id = self.host_org.id
            user.role_id = 1  # Site admin
            user = create_or_update_site_admin(self.site_admin, user)

        user.authkey = self.config.get('site_admin_authkey')
        dump_config = False
        if not user.authkey:  # type: ignore
            dump_config = True
            user.authkey = self.site_admin.get_new_authkey(user)
            self.config['site_admin_authkey'] = user.authkey  # type: ignore
        user.password = self.config.get('site_admin_password')
        if not user.password:
            dump_config = True
            if user.change_pw in ['1', True, 1]:  # type: ignore
                # Only change the password if the user never logged in.
                user.password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                self.site_admin.update_user({'password': user.password, 'change_pw': 0}, user.id)  # type: ignore
            else:
                user.password = 'Already changed by the user'
            self.config['site_admin_password'] = user.password
        self._owner_site_admin = PyMISP(self.baseurl, user.authkey,  # type: ignore
                                        ssl=secure_connection, debug=False, timeout=300)
        self._owner_site_admin.toggle_global_pythonify()
        if dump_config:
            with self.config_file.open('w') as f:
                json.dump(self.config, f, indent=2)
        return self._owner_site_admin

    @property
    def owner_orgadmin(self) -> PyMISP:
        if self._owner_orgadmin:
            return self._owner_orgadmin
        for user in self.site_admin.users():
            if user.email == self.config['email_orgadmin']:
                break
        else:
            # The user doesn't exists
            user = MISPUser()
            user.email = self.config['email_orgadmin']
            user.org_id = self.host_org.id
            user.role_id = 2  # Site admin
            user = self.create_or_update_user(user)

        user.authkey = self.config.get('orgadmin_authkey')
        dump_config = False
        if not user.authkey:  # type: ignore
            dump_config = True
            user.authkey = self.site_admin.get_new_authkey(user)
            self.config['orgadmin_authkey'] = user.authkey  # type: ignore

        user.password = self.config.get('orgadmin_password')
        if not user.password:
            dump_config = True
            if user.change_pw in ['1', True, 1]:  # type: ignore
                # Only change the password if the user never logged in.
                user.password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                self.site_admin.update_user({'password': user.password, 'change_pw': 0}, user.id)  # type: ignore
            else:
                user.password = 'Already changed by the user'
            self.config['orgadmin_password'] = user.password
        # This user might have been disabled by the users
        self._owner_orgadmin = PyMISP(self.baseurl, user.authkey,  # type: ignore
                                      ssl=secure_connection, debug=False, timeout=300)
        self._owner_orgadmin.toggle_global_pythonify()
        if dump_config:
            with self.config_file.open('w') as f:
                json.dump(self.config, f, indent=2)
        return self._owner_orgadmin

    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.docker_compose_root = self.config_file.parent
        with config_file.open() as f:
            self.config = json.load(f)
        self.owner_orgname = self.config['admin_orgname']
        self.baseurl = self.config['baseurl']
        self.hostname = self.config['hostname']
        self.site_admin = PyMISP(self.baseurl, self.config['admin_key'],
                                 ssl=secure_connection, debug=False, timeout=300)
        self.site_admin.toggle_global_pythonify()
        admin_user = self.site_admin.get_user()
        self.site_admin.update_user({'change_pw': 0}, admin_user.id)  # type: ignore

        # Get container name
        cur_dir = os.getcwd()
        os.chdir(self.docker_compose_root)
        command = shlex.split('sudo docker-compose ps -q misp')
        p = Popen(command, stdout=PIPE, stderr=PIPE)
        self.misp_container_name = p.communicate()[0].decode().strip()
        # trash PyMISP so we can update
        command = shlex.split('sudo docker-compose exec -T misp /bin/rm -rf /var/www/MISP/PyMISP')
        Popen(command, stdout=PIPE, stderr=PIPE)
        os.chdir(cur_dir)

        # Make sure the external baseurl is set
        self.update_external_baseurl()
        # init the orgadmin (not site) user
        self.owner_orgadmin

        # Set the default role (id 3 is normal user)
        self.owner_site_admin.set_default_role(3)
        # Set the default sharing level to "All communities"
        self.owner_site_admin.set_server_setting('MISP.default_event_distribution', 3, force=True)
        # Enable taxonomies
        self.enable_default_taxonomies()
        # Set remaining config
        self.owner_site_admin.set_server_setting('MISP.baseurl', self.baseurl, force=True)
        self.owner_site_admin.set_server_setting('MISP.host_org_id', self.host_org.id)
        self.owner_site_admin.set_server_setting('Security.rest_client_baseurl', 'http://127.0.0.1')

    def pass_command_to_docker(self, command):
        cur_dir = os.getcwd()
        os.chdir(self.docker_compose_root)
        c = shlex.split(command)
        p = Popen(c, stdout=PIPE, stderr=PIPE)
        to_return = p.communicate()
        os.chdir(cur_dir)
        return to_return

    def copy_file(self, src, dst):
        '''Copy/paste a file from HOST to the docker filesystem (MISP container)'''
        return self.pass_command_to_docker(f'docker cp {src} {self.misp_container_name}:{dst}')

    def update_external_baseurl(self):
        command = f'sudo docker inspect -f "{{{{.NetworkSettings.Networks.{internal_network_name}.IPAddress}}}}" {self.misp_container_name}'
        outs, errs = self.pass_command_to_docker(command)
        internal_ip = outs.strip().decode()
        external_baseurl = f'http://{internal_ip}'
        if external_baseurl != self.config['external_baseurl']:
            self.config['external_baseurl'] = external_baseurl
            self.update_misp_server_setting('MISP.external_baseurl', external_baseurl)
            with self.config_file.open('w') as f:
                json.dump(self.config, f, indent=2)
        return external_baseurl

    def enable_default_taxonomies(self):
        for taxonomy in self.owner_site_admin.taxonomies():
            if taxonomy.namespace in enabled_taxonomies:
                self.owner_site_admin.enable_taxonomy(taxonomy)

    def update_misp_server_setting(self, key, value):
        self.owner_site_admin.set_server_setting(key, value)

    def change_session_timeout(self, timeout):
        self.update_misp_server_setting('Session.timeout', timeout)
        self.update_misp_server_setting('Session.cookieTimeout', timeout * 10)

    def direct_call(self, url_path, payload=None):
        return self.owner_site_admin.direct_call(url_path, payload)

    def update_misp(self):
        response = self.owner_site_admin.update_misp()
        if response['status'] != 0:
            print(json.dumps(response, indent=2))

    def update_all_json(self):
        self.owner_site_admin.update_object_templates()
        self.owner_site_admin.update_galaxies()
        self.owner_site_admin.update_taxonomies()
        self.owner_site_admin.update_warninglists()
        self.owner_site_admin.update_noticelists()

    def sync_push_all(self):
        for server in self.owner_site_admin.servers():
            self.owner_site_admin.server_push(server)

    def delete_events(self, events):
        for e in events:
            self.owner_site_admin.delete_event(e)

    def create_or_update_user(self, user: MISPUser) -> MISPUser:
        to_return_user = self.owner_site_admin.add_user(user)
        if isinstance(to_return_user, MISPUser):
            return to_return_user
        # The user already exists
        for u in self.owner_site_admin.users():
            if u.email == user.email:
                to_return_user = self.owner_site_admin.update_user(user, u.id)  # type: ignore
                if isinstance(to_return_user, MISPUser):
                    return to_return_user
                raise Exception(f'Unable to update {user.email}: {to_return_user}')
        else:
            raise Exception(f'Unable to create {user.email}: {to_return_user}')

    def create_or_update_tag(self, tag: MISPTag) -> MISPTag:
        to_return_tag = self.owner_site_admin.add_tag(tag)
        if isinstance(to_return_tag, MISPTag):
            return to_return_tag
        # The tag probably already exists
        for t in self.owner_site_admin.tags():
            if t.name == tag.name:
                to_return_tag = self.owner_site_admin.update_tag(tag, t.id)  # type: ignore
                if isinstance(to_return_tag, MISPTag):
                    return to_return_tag
                raise Exception(f'Unable to update {tag.name}: {to_return_tag}')
        else:
            raise Exception(f'Unable to create {tag.name}: {to_return_tag}')

    def create_or_update_organisation(self, organisation: MISPOrganisation) -> MISPOrganisation:
        to_return_org = self.site_admin.add_organisation(organisation)
        if isinstance(to_return_org, MISPOrganisation):
            return to_return_org
        # The organisation is probably already there
        for o in self.site_admin.organisations(scope='all'):
            if o.name == organisation.name:
                to_return_org = self.site_admin.update_organisation(organisation, o.id)
                if isinstance(to_return_org, MISPOrganisation):
                    return self.site_admin.get_organisation(o.id)  # type: ignore
                raise Exception(f'Unable to update {organisation.name}: {to_return_org}')
        else:
            raise Exception(f'Unable to create {organisation.name}: {to_return_org}')

    def init_default_user(self, email, password='Password1234', role_id=1, org_id=None):
        '''Default user is a local admin in the host org'''
        user = MISPUser()
        user.email = email
        if org_id:
            user.org_id = org_id
        else:
            for org in self.owner_site_admin.organisations():
                if org.name == self.config['admin_orgname']:
                    user.org_id = org.id
                    break
            else:
                raise Exception('No default org found.')
        user.role_id = role_id
        user.password = password
        self.create_or_update_user(user)

    def user_statistics(self, context: str='data'):
        return self.owner_site_admin.users_statistics(context)

    def dump_all_events_as_feed(self, root_path: Path):
        feed_dir = root_path / self.owner_orgname
        feed_dir.mkdir(parents=True, exist_ok=True)
        manifest = {}
        hashes = []
        for event in self.owner_site_admin.search(metadata=True):
            e = self.owner_site_admin.get_event(event.uuid, deleted=True)  # type: ignore
            e_feed = e.to_feed(with_meta=True)  # type: ignore
            hashes += [[h, e.uuid] for h in e_feed['Event'].pop('_hashes')]  # type: ignore
            manifest.update(e_feed['Event'].pop('_manifest'))
            with (feed_dir / f'{event.uuid}.json').open('w') as _fw:  # type: ignore
                json.dump(e_feed, _fw, indent=2)
        with (feed_dir / 'hashes.csv').open('w') as hash_file:
            for element in hashes:
                hash_file.write('{},{}\n'.format(element[0], element[1]))
        with (feed_dir / 'manifest.json').open('w') as manifest_file:
            json.dump(manifest, manifest_file, indent=2)

    def create_tag(self, name: str, exportable: bool, reserved: bool):
        tag = MISPTag()
        tag.name = name
        tag.exportable = exportable
        if reserved:
            tag.org_id = self.host_org.id
        self.create_or_update_tag(tag)

    def __repr__(self):
        return f'<{self.__class__.__name__}(external={self.baseurl})>'

    # # Sync config

    def create_sync_user(self, organisation, hostname):
        self.sync_org = self.create_or_update_organisation(organisation)
        email = f"sync_user@{hostname}"
        user = MISPUser()
        user.email = email
        user.org_id = self.sync_org.id
        user.role_id = 5  # Sync user
        sync_user = self.create_or_update_user(user)
        sync_user.authkey = self.owner_site_admin.get_new_authkey(sync_user)

        sync_user_connector = PyMISP(self.owner_site_admin.root_url, sync_user.authkey, ssl=secure_connection, debug=False)
        return sync_user_connector.get_sync_config(pythonify=True)

    def configure_sync(self, server_sync_config, from_central_node=False):
        # Add sharing server
        for s in self.owner_site_admin.servers():
            if s.name == server_sync_config.name:
                server = s
                break
        else:
            print(server_sync_config.to_json())
            server = self.owner_site_admin.import_server(server_sync_config, pythonify=True)
        server.pull = True
        server.push = True  # Not automatic, but allows to do a push
        server.unpublish_event = unpublish_on_sync
        server.url = server_sync_config.url  # In case the internal IP changed, we want to update that.
        server = self.owner_site_admin.update_server(server)
        r = self.owner_site_admin.test_server(server)
        if r['status'] != 1:
            raise Exception(f'Sync test failed: {r}')

        if from_central_node:
            pull_to_create = tag_nodes_to_central
            push_to_create = tag_central_to_nodes
        else:
            pull_to_create = tag_central_to_nodes
            push_to_create = tag_nodes_to_central

        pull_tags = []
        push_tags = []
        # The tags exist.
        for tag in self.owner_site_admin.tags():
            if tag.name in pull_to_create:
                pull_tags.append(tag)
            if tag.name in push_to_create:
                push_tags.append(tag)

        # Set limit on sync config
        if push_tags:
            # # Push
            filter_tag_push = {"tags": {'OR': list(set([t.id for t in push_tags])), 'NOT': []}, 'orgs': {'OR': [], 'NOT': []}}
            server.push_rules = json.dumps(filter_tag_push)
        if pull_tags:
            # # Pull
            filter_tag_pull = {"tags": {'OR': list(set([t.name for t in pull_tags])), 'NOT': []}, 'orgs': {'OR': [], 'NOT': []}}
            server.pull_rules = json.dumps(filter_tag_pull)
            server = self.owner_site_admin.update_server(server)

        # Add sharing group
        for sg in self.owner_site_admin.sharing_groups():
            if sg.name == f'Sharing group with {server_sync_config.Organisation["name"]}':
                self.sharing_group = sg
                break
        else:
            sharing_group = MISPSharingGroup()
            sharing_group.name = f'Sharing group with {server_sync_config.Organisation["name"]}'
            sharing_group.releasability = 'Training'
            self.sharing_group = self.owner_site_admin.add_sharing_group(sharing_group)
            self.owner_site_admin.add_server_to_sharing_group(self.sharing_group, server)
            self.owner_site_admin.add_org_to_sharing_group(self.sharing_group, server_sync_config.Organisation)
            self.owner_site_admin.add_org_to_sharing_group(self.sharing_group, self.host_org)


class MISPInstances():

    central_node_name = central_node_name
    prefix_client_node = prefix_client_node

    def __init__(self, root_misps: str='misps'):
        self.misp_instances_dir = Path(__file__).resolve().parent / root_misps
        self.central_node = MISPInstance(self.misp_instances_dir / self.central_node_name / 'config.json')

        self.client_nodes = {}
        for path in self.misp_instances_dir.glob(f'{self.prefix_client_node}*'):
            if path.name == central_node_name:
                continue
            instance = MISPInstance(path / 'config.json')
            self.client_nodes[instance.owner_orgname] = instance

    def setup_instances(self):
        self.central_node.update_misp()
        self.central_node.update_all_json()
        # Init tags from config
        # # Central Node
        # Locals tags for central node, not sync'ed
        for tagname in local_tags_central:
            self.central_node.create_tag(tagname, False, True)
        # Reserved tags for central node, sync'ed but only selectable by central node org
        for tagname in reserved_tags_central:
            self.central_node.create_tag(tagname, True, True)
        # Tags for sync - Central node to clients
        for tagname in tag_central_to_nodes:
            if tagname in local_tags_central + reserved_tags_central:
                continue
            self.central_node.create_tag(tagname, True, False)

        for tagname in tag_nodes_to_central:
            self.central_node.create_tag(tagname, False, False)

        # # Client Nodes
        for owner_org_name, instance in self.client_nodes.items():
            instance.update_misp()
            instance.update_all_json()
            for tagname in local_tags_clients:
                instance.create_tag(tagname, False, True)
            for tagname in tag_nodes_to_central:
                if tagname in local_tags_clients:
                    continue
                instance.create_tag(tagname, True, False)

            # Initialize sync central node to child
            central_node_sync_config = instance.create_sync_user(self.central_node.host_org, self.central_node.hostname)
            central_node_sync_config.name = f'Sync with {central_node_sync_config.Organisation["name"]}'
            self.central_node.configure_sync(central_node_sync_config, from_central_node=True)

            # Tags pushed by the central node, forbidden to clients.
            for tagname in reserved_tags_central + tag_central_to_nodes:
                instance.create_tag(tagname, False, True)

            sync_server_config = self.central_node.create_sync_user(instance.host_org, instance.hostname)
            sync_server_config.name = f'Sync with {sync_server_config.Organisation["name"]}'
            instance.configure_sync(sync_server_config)

    def setup_sync_all(self):
        instances = list(self.client_nodes.values()) + [self.central_node]
        for instance in instances:
            for remote_instance in instances:
                if remote_instance == instance:
                    continue
                remote_sync_config = remote_instance.create_sync_user(instance.host_org, instance.hostname)
                remote_sync_config.name = f'Sync with {remote_sync_config.Organisation["name"]}'
                instance.configure_sync(remote_sync_config)

    def create_or_update_user_everywhere(self, user: MISPUser):
        self.central_node.create_or_update_user(user)
        for instance in self.client_nodes.values():
            instance.create_or_update_user(user)

    def init_default_user_everywhere(self, email, password='Password1234', role_id=1):
        '''Create admin user in host org user on all instances'''
        self.central_node.init_default_user(email, password, role_id)
        for instance in self.client_nodes.values():
            instance.init_default_user(email, password, role_id)

    def sync_push_all(self):
        self.central_node.sync_push_all()
        for instance in self.client_nodes.values():
            instance.sync_push_all()

    def refresh_external_baseurls(self):
        '''When the docker containers restart, the internal IPs may change.
        This method update the the config files and the sync links'''
        central_node_external_baseurl = self.central_node.update_external_baseurl()
        nodes_external_baseurls = {self.central_node.owner_orgname: central_node_external_baseurl}
        for name, instance in self.client_nodes.items():
            nodes_external_baseurls[name] = instance.update_external_baseurl()

        for server in self.central_node.owner_site_admin.servers():
            instance_name = ' '.join(server.name.split(' ')[-2:])
            if instance_name in nodes_external_baseurls:
                server.url = nodes_external_baseurls[instance_name]
                self.central_node.owner_site_admin.update_server(server)

        for instance in self.client_nodes.values():
            for server in instance.owner_site_admin.servers():
                instance_name = ' '.join(server.name.split(' ')[-2:])
                if instance_name in nodes_external_baseurls:
                    server.url = nodes_external_baseurls[instance_name]
                    instance.owner_site_admin.update_server(server)

    def update_all_instances(self):
        self.central_node.update_misp()
        self.central_node.update_all_json()
        for instance in self.client_nodes.values():
            instance.update_misp()
            instance.update_all_json()

    def cleanup_all_blacklisted_event(self):
        to_delete_on_yt = []
        for instance in self.client_nodes.values():
            blocklists = instance.owner_site_admin.event_blocklists()
            for bl in blocklists:
                to_delete_on_yt.append(bl.event_uuid)
        self.central_node.delete_events(to_delete_on_yt)

        to_delete_on_bts = []
        for bl in self.central_node.owner_site_admin.event_blocklists():
            to_delete_on_bts.append(bl.event_uuid)

        for instance in self.client_nodes.values():
            instance.delete_events(to_delete_on_bts)

    def dump_all_stats(self, dump_to: str):
        dest_dir = Path(dump_to)
        dest_dir.mkdir(exist_ok=True)
        central_node_stats = self.central_node.user_statistics()

        with (dest_dir / f'{self.central_node.owner_orgname}.json').open('w') as f:
            json.dump(central_node_stats, f)

        client_nodes_stats = {}
        for name, instance in self.client_nodes.items():
            client_nodes_stats[name] = instance.user_statistics()

        with (dest_dir / 'clients.json').open('w') as f:
            json.dump(client_nodes_stats, f)

    def dump_all_events(self):
        root_dir = Path('feeds')
        self.central_node.dump_all_events_as_feed(root_dir)
        for name, instance in self.client_nodes.items():
            instance.dump_all_events_as_feed(root_dir)
