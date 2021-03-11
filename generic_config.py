#!/usr/bin/env python3
# -*- coding: utf-8 -*-

internal_network_name = 'custom_misp_training_environment'

# NOTE: There will be an extra instances (the central node), where all the client synchronize with (push)
number_instances = 2

url_scheme = 'http'
central_node_name = 'misp-central'
prefix_client_node = 'misp-'
hostname_suffix = '.local'

# #### Sync config

secure_connection = False
central_node_org_name = 'Central Node'
client_node_org_name_prefix = 'Node '
admin_email_name = 'admin'
orgadmin_email_name = 'orgadmin'

tag_central_to_nodes = ['push_to_nodes', 'push_to_nodes_alt']
tag_nodes_to_central = ['push_to_central', 'push_to_central_alt']

# #### Other config
enabled_taxonomies = ['tlp']
unpublish_on_sync = False

# #### Special tags
# The tags below will only be created on the central or client nodes and marked as non-exportable
# Local tags for central node only
local_tags_central = ['push_to_nodes']
# Global tags, reserved for central node
reserved_tags_central = ['push_to_nodes_alt']
# Tags reserved for the clients
local_tags_clients = ['push_to_central_alt']
