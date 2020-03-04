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

number_instances = 5
# NOTE: There will be an extra instances (the central node), where all the client synchronize with (push)

internal_network_name = 'custom_misp_training_environment'


def prepare_docker_compose(path, http_port, https_port):
    with (path / 'docker-compose.yml').open() as f:
        docker_content = f.read()
    docker_content = docker_content.replace('80:80', f'{http_port}:80')
    docker_content = docker_content.replace('443:443', f'{https_port}:443')

    # Add refresh script
    if docker_content.find('misp-refresh') < 0:
        docker_content = docker_content.replace('volumes:', 'volumes:\n      - "../../misp-refresh:/var/www/MISP/misp-refresh/"')

    # Add network configuration so all the containers are on the same
    if docker_content.find('networks') < 0:
        docker_content = docker_content.replace('#      - "NOREDIR=true" #Do not redirect port 80', '      - "NOREDIR=true" #Do not redirect port 80\n    networks:\n        - default\n        - misp-test-sync')
        docker_content += f'\nnetworks:\n    misp-test-sync:\n        external:\n            name: {internal_network_name}\n'

    with (path / 'docker-compose.yml').open('w') as f:
        f.write(docker_content)


def run_docker(path):
    cur_dir = os.getcwd()
    os.chdir(path)
    # Build the dockers
    command = shlex.split('sudo docker-compose -f docker-compose.yml -f build-docker-compose.yml build')
    p = Popen(command)
    p.wait()
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
    return ip


def initial_misp_setup(path, config):
    cur_dir = os.getcwd()
    os.chdir(path)
    # Init admin user
    command = shlex.split('sudo docker-compose exec misp /bin/bash /var/www/MISP/app/Console/cake userInit')
    p = Popen(command)
    p.wait()
    # Set baseurl
    command = shlex.split(f'sudo docker-compose exec misp /bin/bash /var/www/MISP/app/Console/cake baseurl {config["baseurl"]}')
    p = Popen(command)
    p.wait()
    # Run DB updates
    command = shlex.split('sudo docker-compose exec --user www-data misp /bin/bash /var/www/MISP/app/Console/cake Admin runUpdates')
    p = Popen(command)
    p.wait()
    # Set the admin key
    command = shlex.split(f'sudo docker-compose exec misp /bin/bash /var/www/MISP/app/Console/cake admin change_authkey admin@admin.test {config["admin_key"]}')
    p = Popen(command)
    p.wait()
    os.chdir(cur_dir)


# Initialize all the repositories containing the docker images
misp_instances_dir = Path('misps')
misp_instances_dir.mkdir(exist_ok=True)
master_repo = git.Repo('.')
width = len(str(number_instances))
for instance_id in range(number_instances + 1):
    if instance_id == 0:
        # Central node
        misp_docker_dir = misp_instances_dir / 'misp_central'
    else:
        misp_docker_dir = misp_instances_dir / 'misp{0:0{width}}'.format(instance_id, width=width)
    if misp_docker_dir.exists():
        instance_repo = git.Repo(misp_docker_dir)
        instance_repo.git.checkout('docker-compose.yml')
        instance_repo.remote('origin').pull()
    else:
        instance_repo = git.repo.base.Repo.clone_from('https://github.com/coolacid/docker-misp.git', str(misp_docker_dir))

    config = {
        'http_port': f'80{instance_id}',
        'https_port': f'443{instance_id}',
        'baseurl': f'https://localhost:443{instance_id}/',
        'admin_key': ''.join(random.choices(string.ascii_uppercase + string.digits, k=40))
    }

    prepare_docker_compose(misp_docker_dir, config['http_port'], config['https_port'])

    # Initialize network (does nothing if already existing)
    command = shlex.split(f'sudo docker network create {internal_network_name}')
    p = Popen(command)
    p.wait()

    ip = run_docker(misp_docker_dir)
    config['external_baseurl'] = f'http://{ip}'

    initial_misp_setup(misp_docker_dir, config)

    with (misp_docker_dir / 'config.json').open('w') as f:
        json.dump(config, f, indent=2)
