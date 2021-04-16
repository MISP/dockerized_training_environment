#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from misp_instances import MISPInstances

url = ''
data = """
{
}
"""


if __name__ == '__main__':
    json_data = json.loads(data)
    instances = MISPInstances()
    instances.central_node.direct_call(url, json_data)
    for node in instances.client_nodes.values():
        node.direct_call(url, json_data)
