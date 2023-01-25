#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from generic_config import internal_network_name, cert_name
import yaml

docker_compose_file = Path('nginx-proxy/docker-compose.yml')

with docker_compose_file.open() as f:
    a = f.read()
    docker_content = yaml.safe_load(a)

if docker_content['version'] == '2':
    docker_content['version'] = '3'

if not docker_content['services']['nginx-proxy'].get('networks'):
    docker_content['services']['nginx-proxy']['networks'] = ['default', 'misp-test-sync']
    docker_content['networks'] = {'misp-test-sync': {'external': {'name': internal_network_name}}}

if '443:443' not in docker_content['services']['nginx-proxy']['ports']:
    docker_content['services']['nginx-proxy']['ports'].append('443:443')

if Path('certs').exists() and '../certs:/etc/nginx/certs' not in docker_content['services']['nginx-proxy']['volumes']:
    docker_content['services']['nginx-proxy']['volumes'].append('../certs:/etc/nginx/certs')

if Path('nginx.tmpl').exists() and '../nginx.tmpl:/app/nginx.tmpl' not in docker_content['services']['nginx-proxy']['volumes']:
    docker_content['services']['nginx-proxy']['volumes'].append('../nginx.tmpl:/app/nginx.tmpl')

if cert_name:
    if not docker_content['services']['nginx-proxy'].get('environment'):
        docker_content['services']['nginx-proxy']['environment'] = []
    if f"CERT_NAME='{cert_name}'" not in docker_content['services']['nginx-proxy']['environment']:
        docker_content['services']['nginx-proxy']['environment'].append(f"CERT_NAME='{cert_name}'")


with docker_compose_file.open('w') as f:
    f.write(yaml.dump(docker_content, default_flow_style=False))
