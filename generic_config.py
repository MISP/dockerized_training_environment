#!/usr/bin/env python3
# -*- coding: utf-8 -*-

internal_network_name = 'custom_misp_training_environment'

# NOTE: There will be an extra instances (the central node), where all the client synchronize with (push)
number_instances = 2

# Name of the TLS certificate to use for https connection.
# NOTE: you must have files called <cert_name>.crt and <cert_name>.key in the certs directory
cert_name = ''

url_scheme = 'http'
central_node_name = 'misp-central'
prefix_client_node = 'misp-'
hostname_suffix = '.local'

instances_number_width = len(str(number_instances))
client_node_name_getter = None
# client_node_name_getter = (
#     lambda instance_id: f"{prefix_client_node}{instance_id:0{instances_number_width}}"
# )
# mapping = {
#     0: 'NATO-MN-MISP',
#     1: 'NATO',
#     2: 'ALB',
#     3: 'BEL',
#     4: 'BGR',
#     5: 'XYZ',
# }
# client_node_name_getter = (
#     lambda instance_id: f"{prefix_client_node}{mapping[instance_id]}"
# )

# #### Sync config

secure_connection = False
central_node_org_name = 'Central Node'
client_node_org_name_prefix = 'Node '
admin_email_name = 'admin'
orgadmin_email_name = 'orgadmin'
client_node_org_name_getter = None
# client_node_org_name_getter = lambda instance_id: f'{client_node_org_name_prefix}{instance_id:0{instances_number_width}}'
# client_node_org_name_getter = (
#     lambda instance_id: f"{client_node_org_name_prefix}{mapping[instance_id]}"
# )


tag_central_to_nodes = ['push_to_nodes', 'push_to_nodes_alt']
tag_nodes_to_central = ['push_to_central', 'push_to_central_alt']

# #### Other config
enabled_taxonomies = ['tlp']
enabled_taxonomies_central_node = []
unpublish_on_sync = False

central_node_server_settings = {
}

# #### Special tags
# The tags below will only be created on the central or client nodes and marked as non-exportable
# Local tags for central node only
local_tags_central = ['push_to_nodes']
# Global tags, reserved for central node
reserved_tags_central = ['push_to_nodes_alt']
# Tags reserved for the clients
local_tags_clients = ['push_to_central_alt']


additional_orgs_per_instance = None
# additional_orgs_per_instance = {
#     1: [],
#     2: [],
#     3: ["CERT-BE"],
#     4: ["CERT-BE"],
#     5: ["foo", "bar"],
# }

# Additional sharing groups. Provisioned on all instances.
# Note: central_node_org_name is always included in the SG
additional_sharinggroups = None
# additional_sharinggroups = {
#     "Nato Countries": [
#         f"{client_node_org_name_prefix}NATO",
#         f"{client_node_org_name_prefix}ALB",
#         f"{client_node_org_name_prefix}BEL",
#         f"{client_node_org_name_prefix}BGR",
#     ],
#     "7NNNs": [
#         f"{client_node_org_name_prefix}XYZ",
#     ],
#     "Partners": [
#         f"{client_node_org_name_prefix}BGR",
#     ],
#     "National Civilian Organizations": [
#         f"{client_node_org_name_prefix}BGR",
#         f"{client_node_org_name_prefix}XYZ",
#     ],
# }
