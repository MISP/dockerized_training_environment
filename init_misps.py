#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
import git
from subprocess import Popen, PIPE
import shlex
import os
import random
import string
import yaml

from generic_config import (internal_network_name, number_instances, central_node_name,
                            hostname_suffix, prefix_client_node, admin_email_name, orgadmin_email_name,
                            central_node_org_name, client_node_org_name_prefix, url_scheme)


class MISPDocker():

    def __init__(self, root_dir: Path, instance_id: int, instances_number_width: int, url_scheme: str):
        self.instance_id = instance_id
        self.url_scheme = url_scheme
        self.config = {
            'http_port': f'80{self.instance_id}',
            'https_port': f'443{self.instance_id}',
            'admin_key': ''.join(random.choices(string.ascii_uppercase + string.digits, k=40)),
        }

        if self.instance_id == 0:
            self.misp_docker_dir = root_dir / central_node_name
            self.config['baseurl'] = f'{url_scheme}://{central_node_name}{hostname_suffix}'
            self.config['hostname'] = f'{central_node_name}{hostname_suffix}'
            self.config['email_site_admin'] = f"{admin_email_name}@{self.config['hostname']}"
            self.config['email_orgadmin'] = f"{orgadmin_email_name}@{self.config['hostname']}"
            self.config['admin_orgname'] = central_node_org_name
            self.config['certname'] = f'{hostname_suffix}'.lstrip('.')
        else:
            client_name = f'{prefix_client_node}{instance_id:0{instances_number_width}}'
            self.misp_docker_dir = root_dir / client_name
            self.config['baseurl'] = f'{url_scheme}://{client_name}{hostname_suffix}'
            self.config['hostname'] = f'{client_name}{hostname_suffix}'
            self.config['email_site_admin'] = f"{admin_email_name}@{self.config['hostname']}"
            self.config['email_orgadmin'] = f"{orgadmin_email_name}@{self.config['hostname']}"
            self.config['admin_orgname'] = f'{client_node_org_name_prefix}{instance_id:0{instances_number_width}}'
            self.config['certname'] = f'{instance_id:0{instances_number_width}}{hostname_suffix}'

        if self.misp_docker_dir.exists():
            self.instance_repo = git.Repo(self.misp_docker_dir)
            self.instance_repo.git.checkout('docker-compose.yml')
            self.instance_repo.remote('origin').pull()
        else:
            self.instance_repo = git.repo.base.Repo.clone_from('https://github.com/coolacid/docker-misp.git', str(self.misp_docker_dir))

        self._prepare_docker_compose()

    @property
    def hostsfile_entry(self):
        return f"127.0.0.1    {self.config['hostname']}"

    def _prepare_docker_compose(self):
        with (self.misp_docker_dir / 'docker-compose.yml').open() as f:
            docker_content = yaml.safe_load(f.read())

        docker_content['services']['misp']['ports'] = [f'{self.config["http_port"]}:80',
                                                       f'{self.config["https_port"]}:443']

        # Add refresh script
        if '../../misp-refresh:/var/www/MISP/misp-refresh/' not in docker_content['services']['misp']['volumes']:
            # Add misp-refresh
            docker_content['services']['misp']['volumes'].append('../../misp-refresh:/var/www/MISP/misp-refresh/')

        # Add network configuration so all the containers are on the same
        if not docker_content['services']['misp'].get('networks'):
            docker_content['services']['misp']['environment'].append('NOREDIR=true')
            docker_content['services']['misp']['environment'].append(f'VIRTUAL_HOST={self.config["hostname"]}')
            docker_content['services']['misp']['environment'].append(f'CERT_NAME={self.config["certname"]}')
            docker_content['services']['misp']['networks'] = ['default', 'misp-test-sync']

            docker_content['networks'] = {'misp-test-sync': {'external': {'name': internal_network_name}}}

        with (self.misp_docker_dir / 'docker-compose.yml').open('w') as f:
            f.write(yaml.dump(docker_content, default_flow_style=False))

        cur_dir = os.getcwd()
        os.chdir(self.misp_docker_dir)
        # Build the dockers
        command = shlex.split('sudo docker-compose -f docker-compose.yml -f build-docker-compose.yml build')
        p = Popen(command)
        p.wait()
        os.chdir(cur_dir)

    def dump_config(self):
        with (self.misp_docker_dir / 'config.json').open('w') as f:
            json.dump(self.config, f, indent=2)

    def load_config(self) -> dict:
        with (self.misp_docker_dir / 'config.json').open() as f:
            return json.load(f)

    def run(self):
        cur_dir = os.getcwd()
        os.chdir(self.misp_docker_dir)
        # Run the dockers
        command = shlex.split('sudo docker-compose up -d')
        p = Popen(command)
        p.wait()
        # Get IP on docker
        # # Get thing to inspect
        command = shlex.split('sudo docker-compose ps -q misp')
        p = Popen(command, stdout=PIPE)
        thing = p.communicate()[0].decode().strip()
        # Yes, 4 {, we need 2 in the output string
        command = shlex.split(f'sudo docker inspect -f "{{{{.NetworkSettings.Networks.{internal_network_name}.IPAddress}}}}"')
        command.append(thing)
        p = Popen(command, stdout=PIPE)
        ip = p.communicate()[0].decode().strip()
        os.chdir(cur_dir)
        self.config['external_baseurl'] = f'http://{ip}'

    def initial_misp_setup(self):
        cur_dir = os.getcwd()
        os.chdir(self.misp_docker_dir)
        # Init admin user
        command = shlex.split('sudo docker-compose exec misp /bin/bash /var/www/MISP/app/Console/cake userInit')
        p = Popen(command)
        p.wait()
        # Set baseurl
        command = shlex.split(f'sudo docker-compose exec --user www-data misp /bin/bash /var/www/MISP/app/Console/cake baseurl {self.config["baseurl"]}')
        p = Popen(command)
        p.wait()
        # Run DB updates
        command = shlex.split('sudo docker-compose exec --user www-data misp /bin/bash /var/www/MISP/app/Console/cake Admin runUpdates')
        p = Popen(command)
        p.wait()
        # Set the admin key
        command = shlex.split(f'sudo docker-compose exec misp /bin/bash /var/www/MISP/app/Console/cake admin change_authkey admin@admin.test {self.config["admin_key"]}')
        p = Popen(command)
        p.wait()
        # Turn the instance live
        command = shlex.split(f'sudo docker-compose exec --user www-data misp /bin/bash /var/www/MISP/app/Console/cake live 1')
        p = Popen(command)
        p.wait()
        os.chdir(cur_dir)


class MISPDockerManager():

    internal_network_name = internal_network_name
    number_instances = number_instances
    central_node_name = central_node_name
    hostname_suffix = hostname_suffix
    prefix_client_node = prefix_client_node
    admin_email_name = admin_email_name
    orgadmin_email_name = orgadmin_email_name
    central_node_org_name = central_node_org_name
    client_node_org_name_prefix = client_node_org_name_prefix
    url_scheme = url_scheme

    def __init__(self, root_misps: str='misps'):
        # Initialize all the repositories containing the docker images
        self.misp_instances_dir = Path(root_misps)
        self.misp_instances_dir.mkdir(exist_ok=True)
        self.master_repo = git.Repo('.')
        self.width = len(str(self.number_instances))
        # NOTE: self.misp_dockers[0] is the central node.
        self.misp_dockers = []
        self._create_docker_internal_network()

    def _create_docker_internal_network(self):
        # Initialize network (does nothing if already existing)
        command = shlex.split(f'sudo docker network create {self.internal_network_name}')
        p = Popen(command)
        p.wait()

    @property
    def hostsfile(self) -> str:
        for_hostsfile = ''
        for misp_docker in self.misp_dockers:
            for_hostsfile += misp_docker.hostsfile_entry + '\n'
        return for_hostsfile

    def initialize_config_files(self):
        for instance_id in range(self.number_instances + 1):
            misp_docker = MISPDocker(self.misp_instances_dir, instance_id, self.width, self.url_scheme)
            self.misp_dockers.append(misp_docker)

    def run_dockers(self):
        for misp_docker in self.misp_dockers:
            misp_docker.run()
            misp_docker.initial_misp_setup()
            misp_docker.dump_config()


if __name__ == '__main__':
    manager = MISPDockerManager()
    manager.initialize_config_files()
    manager.run_dockers()

    print('Entries for /etc/hosts:')
    print(manager.hostsfile)

    print('If there were any errors, re-run te script before setting up the sync, or it will fail.')
