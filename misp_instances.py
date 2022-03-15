#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import random
import shlex
import string

from subprocess import Popen, PIPE
from pathlib import Path

from pymisp import PyMISP, MISPUser

from generic_config import (central_node_name, prefix_client_node, secure_connection, internal_network_name)


class MISPInstance():
    owner_orgname: str
    site_admin: PyMISP
    owner_site_admin: PyMISP
    owner_orgadmin: PyMISP

    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.docker_compose_root = self.config_file.parent
        with config_file.open() as f:
            self.config = json.load(f)
        self.owner_orgname = self.config['admin_orgname']
        self.site_admin = PyMISP(self.config['baseurl'], self.config['admin_key'],
                                 ssl=secure_connection, debug=False)

        dump_config = False
        # Initialize connectors for other main accounts
        for user in self.site_admin.users(pythonify=True):
            if user.email == self.config['email_site_admin']:
                user.authkey = self.config.get('site_admin_authkey')
                if not user.authkey:
                    dump_config = True
                    user.authkey = self.site_admin.get_new_authkey(user)
                    self.config['site_admin_authkey'] = user.authkey
                user.password = self.config.get('site_admin_password')
                if not user.password:
                    dump_config = True
                    if user.change_pw in ['1', True, 1]:
                        # Only change the password if the user never logged in.
                        user.password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                        self.site_admin.update_user({'password': user.password}, user.id)
                    else:
                        user.password = 'Already changed by the user'
                    self.config['site_admin_password'] = user.password

                self.owner_site_admin = PyMISP(self.config['baseurl'], user.authkey,
                                               ssl=secure_connection, debug=False)
            if user.email == self.config['email_orgadmin']:
                try:
                    user.authkey = self.config.get('orgadmin_authkey')
                    if not user.authkey:
                        dump_config = True
                        user.authkey = self.site_admin.get_new_authkey(user)
                        self.config['orgadmin_authkey'] = user.authkey

                    user.password = self.config.get('orgadmin_password')
                    if not user.password:
                        dump_config = True
                        if user.change_pw in ['1', True, 1]:
                            # Only change the password if the user never logged in.
                            user.password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                            self.site_admin.update_user({'password': user.password}, user.id)
                        else:
                            user.password = 'Already changed by the user'
                        self.config['orgadmin_password'] = user.password
                    # This user might have been disabled by the users
                    self.owner_orgadmin = PyMISP(self.config['baseurl'], user.authkey,
                                                 ssl=secure_connection, debug=False)
                except Exception:
                    self.owner_orgadmin = None

        if dump_config:
            with self.config_file.open('w') as f:
                json.dump(self.config, f, indent=2)
        # Get container name
        cur_dir = os.getcwd()
        os.chdir(self.docker_compose_root)
        command = shlex.split('sudo docker-compose ps -q misp')
        p = Popen(command, stdout=PIPE, stderr=PIPE)
        self.misp_container_name = p.communicate()[0].decode().strip()
        os.chdir(cur_dir)

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

    def get_current_external_baseurl(self):
        command = f'sudo docker inspect -f "{{{{.NetworkSettings.Networks.{internal_network_name}.IPAddress}}}}" {self.misp_container_name}'
        outs, errs = self.pass_command_to_docker(command)
        internal_ip = outs.strip()
        external_baseurl = f'http://{internal_ip}'
        if external_baseurl != self.config['external_baseurl']:
            self.config['external_baseurl'] = external_baseurl
            self.update_misp_server_setting('MISP.external_baseurl', external_baseurl)
            with self.config_file.open('w') as f:
                json.dump(self.config, f, indent=2)
        return external_baseurl

    def update_misp_server_setting(self, key, value):
        self.owner_site_admin.set_server_setting(key, value)

    def change_session_timeout(self, timeout):
        self.update_misp_server_setting('Session.timeout', timeout)
        self.update_misp_server_setting('Session.cookieTimeout', timeout * 10)

    def direct_call(self, url_path, payload=None):
        return self.owner_site_admin.direct_call(url_path, payload)

    def update_misp(self):
        self.owner_site_admin.update_misp()

    def update_all_json(self):
        self.owner_site_admin.update_object_templates()
        self.owner_site_admin.update_galaxies()
        self.owner_site_admin.update_taxonomies()
        self.owner_site_admin.update_warninglists()
        self.owner_site_admin.update_noticelists()

    def sync_push_all(self):
        for server in self.owner_site_admin.servers(pythonify=True):
            self.owner_site_admin.server_push(server)

    def delete_events(self, events):
        for e in events:
            self.owner_site_admin.delete_event(e)

    def create_or_update_user(self, user: MISPUser) -> MISPUser:
        to_return_user = self.owner_site_admin.add_user(user, pythonify=True)
        if isinstance(to_return_user, MISPUser):
            return to_return_user
        # The user already exists
        for u in self.owner_site_admin.users(pythonify=True):
            if u.email == user.email:
                to_return_user = self.owner_site_admin.update_user(user, u.id, pythonify=True)
                if isinstance(to_return_user, MISPUser):
                    return to_return_user
                raise Exception(f'Unable to update {user.email}: {to_return_user}')
        else:
            raise Exception(f'Unable to create {user.email}: {to_return_user}')

    def init_default_user(self, email, password='Password1234', role_id=1, org_id=None):
        '''Default user is a local admin in the host org'''
        user = MISPUser()
        user.email = email
        if org_id:
            user.org_id = org_id
        else:
            for org in self.owner_site_admin.organisations(pythonify=True):
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
        for event in self.owner_site_admin.search(metadata=True, pythonify=True):
            e = self.owner_site_admin.get_event(event.uuid, deleted=True, pythonify=True)
            e_feed = e.to_feed(with_meta=True)
            hashes += [[h, e.uuid] for h in e_feed['Event'].pop('_hashes')]
            manifest.update(e_feed['Event'].pop('_manifest'))
            with (feed_dir / f'{event.uuid}.json').open('w') as _fw:
                json.dump(e_feed, _fw, indent=2)
        with (feed_dir / 'hashes.csv').open('w') as hash_file:
            for element in hashes:
                hash_file.write('{},{}\n'.format(element[0], element[1]))
        with (feed_dir / 'manifest.json').open('w') as manifest_file:
            json.dump(manifest, manifest_file, indent=2)


class MISPInstances():

    central_node_name = central_node_name
    prefix_client_node = prefix_client_node

    def __init__(self, root_misps: str='misps'):
        self.misp_instances_dir = Path(__file__).resolve().parent / root_misps
        self.central_node = MISPInstance(self.misp_instances_dir / self.central_node_name / 'config.json')

        self.client_nodes = {}
        for path in self.misp_instances_dir.glob(f'{self.prefix_client_node}*'):
            instance = MISPInstance(path / 'config.json')
            self.client_nodes[instance.owner_orgname] = instance

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
        central_node_external_baseurl = self.central_node.get_current_external_baseurl()
        nodes_external_baseurls = {self.central_node.owner_orgname: central_node_external_baseurl}
        for name, instance in self.client_nodes.items():
            nodes_external_baseurls[name] = instance.get_current_external_baseurl()

        for server in self.central_node.owner_site_admin.servers(pythonify=True):
            instance_name = ' '.join(server.name.split(' ')[-2:])
            if instance_name in nodes_external_baseurls:
                server.url = nodes_external_baseurls[instance_name]
                self.central_node.owner_site_admin.update_server(server)

        for instance in self.client_nodes.values():
            for server in instance.owner_site_admin.servers(pythonify=True):
                instance_name = ' '.join(server.name.split(' ')[-2:])
                if instance_name in nodes_external_baseurls:
                    server.url = nodes_external_baseurls[instance_name]
                    self.central_node.owner_site_admin.update_server(server)

    def cleanup_all_blacklisted_event(self):
        to_delete_on_yt = []
        for instance in self.client_nodes.values():
            blocklists = instance.owner_site_admin.event_blocklists(pythonify=True)
            for bl in blocklists:
                to_delete_on_yt.append(bl.event_uuid)
        self.central_node.delete_events(to_delete_on_yt)

        to_delete_on_bts = []
        for bl in self.central_node.owner_site_admin.event_blocklists(pythonify=True):
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
