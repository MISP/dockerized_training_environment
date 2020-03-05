#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from generic_config import internal_network_name

docker_compose_file = Path('nginx-proxy/docker-compose.yml')


with docker_compose_file.open() as f:
    docker_content = f.read()

if docker_content.find("version: '2'") == 0:
    docker_content = docker_content.replace("version: '2'", "version: '3'")

if docker_content.find('networks') < 0:
    add_network = """
      - /var/run/docker.sock:/tmp/docker.sock:ro

    networks:
      - default
      - misp-test-sync
"""
    docker_content = docker_content.replace('      - /var/run/docker.sock:/tmp/docker.sock:ro', add_network)
    add_external_network = f"""
networks:
    misp-test-sync:
        external:
            name: {internal_network_name}
"""
    docker_content += add_external_network

with docker_compose_file.open('w') as f:
    f.write(docker_content)
