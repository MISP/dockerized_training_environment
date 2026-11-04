#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render the training environment described by a config file as a static HTML page
meant to be screenshotted: the central node, one box per team instance (number, name,
URL) and tables of the *effective* additional sharing groups and their members.
Config problems are printed in the terminal, not on the page.

"Effective" mirrors what MISPInstances.setup_instances() really provisions:
  * the central org is always added to each sharing group,
  * members that do not exist as an org (host org of an instance or an
    additional org) are skipped,
  * duplicates collapse into a single member.

Usage:
    python show_topology.py                       # reads generic_config.py, opens browser
    python show_topology.py -c other_config.py -o /tmp/topo.html --no-open
"""

import argparse
import html
import runpy
import sys
import webbrowser
from pathlib import Path


def load_config(path: Path) -> dict:
    try:
        return runpy.run_path(str(path))
    except Exception as e:
        sys.exit(f'Unable to load {path}: {type(e).__name__}: {e}')


def build_model(cfg: dict) -> dict:
    number_instances = cfg['number_instances']
    width = len(str(number_instances))
    prefix_node = cfg.get('prefix_client_node', 'misp-')
    prefix_org = cfg.get('client_node_org_name_prefix', 'team-')
    suffix = cfg.get('hostname_suffix', '')
    scheme = cfg.get('url_scheme', 'https')
    name_getter = cfg.get('client_node_name_getter')
    org_getter = cfg.get('client_node_org_name_getter')
    mapping = cfg.get('mapping') or {}
    additional_orgs = cfg.get('additional_orgs_per_instance') or {}
    sharing_groups = cfg.get('additional_sharinggroups') or {}
    central_org = cfg['central_node_org_name']
    central_name = cfg['central_node_name']

    warnings = []

    # Same logic as init_misps.MISPDocker: instance 0 is the central node, 1..N are clients
    instances = []
    for instance_id in range(1, number_instances + 1):
        node = name_getter(instance_id) if name_getter else f'{prefix_node}{instance_id:0{width}}'
        org = org_getter(instance_id) if org_getter else f'{prefix_org}{instance_id:0{width}}'
        instances.append({
            'id': instance_id,
            'org': org,
            'label': org[len(prefix_org):] if org.startswith(prefix_org) else org,
            'unassigned': bool(mapping) and instance_id not in mapping,
            'url': f'{scheme}://{node}{suffix}',
            'extra_orgs': list(additional_orgs.get(instance_id, [])),
        })
        if mapping and instance_id not in mapping:
            warnings.append(f'Instance {instance_id} has no entry in `mapping`: it will be named "{org}"')

    for instance_id in additional_orgs:
        if not 1 <= instance_id <= number_instances:
            warnings.append(f'additional_orgs_per_instance has an entry for instance {instance_id}, which does not exist')

    existing_orgs = {central_org} | {i['org'] for i in instances}
    existing_orgs |= {o for orgs in additional_orgs.values() for o in orgs}

    seen_orgs = {}
    for i in instances:
        if i['org'] in seen_orgs:
            warnings.append(f'Instances {seen_orgs[i["org"]]} and {i["id"]} share the org name "{i["org"]}"')
        seen_orgs.setdefault(i['org'], i['id'])

    groups = []
    for sg_name, members in sharing_groups.items():
        effective, skipped, dupes = [central_org], [], []
        for org in members:
            if org not in existing_orgs:
                skipped.append(org)
            elif org in effective:
                if org != central_org:
                    dupes.append(org)
            else:
                effective.append(org)
        groups.append({'name': sg_name, 'members': effective, 'skipped': skipped, 'dupes': dupes})

    missing: dict[str, list[str]] = {}
    for g in groups:
        for org in g['skipped']:
            missing.setdefault(org, []).append(g['name'])
    for org, sg_names in missing.items():
        warnings.append(f'Org "{org}" does not exist: skipped in {len(sg_names)} sharing group(s) ({", ".join(sg_names)})')

    in_any_sg = {org for g in groups for org in g['members']}
    for i in instances:
        if groups and i['org'] not in in_any_sg:
            warnings.append(f'Instance {i["id"]} ({i["org"]}) is in no additional sharing group')

    return {
        'central': {'org': central_org, 'url': f'{scheme}://{central_name}{suffix}'},
        'instances': instances,
        'groups': groups,
        'warnings': warnings,
        'width': width,
        'org_prefix': prefix_org,
    }


def check_instance_dirs(cfg: dict, model: dict, misps_dir: Path) -> None:
    """Flag directories in misps/ that the current config would not create.
    MISPInstances() loads every `<prefix_client_node>*` directory, so stale ones get picked up as clients."""
    if not misps_dir.is_dir():
        return
    expected = {i['url'].split('://', 1)[1].removesuffix(cfg.get('hostname_suffix', '')) for i in model['instances']}
    central = cfg['central_node_name']
    if not (misps_dir / central).is_dir() and any(p.is_dir() for p in misps_dir.iterdir()):
        model['warnings'].append(f'Central node directory {misps_dir.name}/{central} does not exist yet')
    for path in sorted(misps_dir.glob(f'{cfg.get("prefix_client_node", "misp-")}*')):
        if path.is_dir() and path.name not in expected and path.name != central:
            model['warnings'].append(f'Stale directory {misps_dir.name}/{path.name}: not part of this config, '
                                     'but MISPInstances() will still load it as a client node')


def print_summary(model: dict) -> None:
    print(f'Central node: {model["central"]["org"]}  ({model["central"]["url"]})')
    print(f'{len(model["instances"])} client instances, each synchronising with the central node:')
    w = model['width']
    for i in model['instances']:
        extra = f'  + {", ".join(i["extra_orgs"])}' if i['extra_orgs'] else ''
        print(f'  Team {i["id"]:0{w}}  {i["label"]:<24} {i["url"]}{extra}')
    print('\nEffective sharing groups (central org always included):')
    for g in model['groups']:
        print(f'  [{len(g["members"]):>2}] {g["name"]}')
    if model['warnings']:
        print('\nWarnings:')
        for warning in model['warnings']:
            print(f'  ! {warning}')


SG_COLORS = ['#2563eb', '#c2410c', '#047857', '#be185d', '#6d28d9', '#0e7490', '#4d7c0f', '#b91c1c', '#4338ca', '#a16207']


def render_html(model: dict, config_path: Path, matrix_columns: int = 2) -> str:
    esc = html.escape
    w = model['width']
    central = model['central']
    groups = model['groups']
    host = lambda url: url.split('://', 1)[-1]
    scheme = central['url'].split('://', 1)[0]
    prefix = model['org_prefix']

    # Team boxes
    boxes = []
    for i in model['instances']:
        extra = ''.join(f'<div class="extra">+ {esc(o)}</div>' for o in i['extra_orgs'])
        boxes.append(f'<div class="team"><div class="top"><span class="num">{i["id"]:0{w}}</span>'
                     f'<span class="name{' unassigned' if i['unassigned'] else ''}">{'unassigned' if i['unassigned'] else esc(i['label'])}</span></div>'
                     f'<div class="url">{esc(host(i["url"]))}</div>{extra}</div>')

    # Sharing group legend table
    any_skipped = any(g['skipped'] for g in groups)
    legend_rows = []
    for idx, g in enumerate(groups):
        color = SG_COLORS[idx % len(SG_COLORS)]
        skipped = f'<td class="skipped">{esc(", ".join(g["skipped"]))}</td>' if any_skipped else ''
        legend_rows.append(f'<tr><td><span class="tag" style="--c:{color}">SG{idx + 1}</span></td>'
                           f'<td>{esc(g["name"])}</td><td class="n">{len(g["members"])}</td>{skipped}</tr>')
    legend = (f'<table class="legend"><thead><tr><th></th><th>Sharing group</th><th class="n">Orgs</th>'
              f'{"<th>Not found (skipped)</th>" if any_skipped else ""}</tr></thead>'
              f'<tbody>{"".join(legend_rows)}</tbody></table>') if groups else '<p class="muted">No additional sharing groups configured.</p>'

    # Membership matrix: one row per org (central, each team, then its additional orgs)
    rows = [('00', central['org'], f'{central["org"]} (central)', 'central-row')]
    for i in model['instances']:
        rows.append((f'{i["id"]:0{w}}', i['org'], i['label'] + (' (unassigned)' if i['unassigned'] else ''), ''))
        rows += [('', o, o.removeprefix(prefix), 'sub') for o in i['extra_orgs']]
    member_sets = [set(g['members']) for g in groups]
    head = ''.join(f'<th class="c"><span class="tag" style="--c:{SG_COLORS[k % len(SG_COLORS)]}">SG{k + 1}</span></th>'
                   for k in range(len(groups)))
    body = []
    for num, org, label, cls in rows:
        cells = ''.join(
            f'<td class="c">{"<span class=dot style=--c:" + SG_COLORS[k % len(SG_COLORS)] + "></span>" if org in s else ""}</td>'
            for k, s in enumerate(member_sets))
        body.append(f'<tr class="{cls}"><td class="num">{num}</td><td>{esc(label)}</td>{cells}</tr>')
    # Split the membership table in side-by-side chunks so the page stays short enough for a screenshot
    per_chunk = -(-len(body) // matrix_columns)
    matrix = ''.join(
        f'<table class="matrix"><thead><tr><th>#</th><th>Team</th>{head}</tr></thead>'
        f'<tbody>{"".join(body[k:k + per_chunk])}</tbody></table>'
        for k in range(0, len(body), per_chunk)) if groups else ''

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Training Environment Topology</title>
<style>
:root {{ --bg: #ffffff; --fg: #1a1a18; --muted: #6b6b66; --line: #dcdcd6; --soft: #f5f5f2; --dark: #1f2937; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg); font: 13px/1.35 system-ui, -apple-system, "Segoe UI", sans-serif; }}
.page {{ padding: 20px 24px; }}
h1 {{ font-size: 18px; margin: 0 0 2px; }}
.sub-title {{ color: var(--muted); margin-bottom: 18px; }}
h2 {{ font-size: 14px; margin: 0 0 8px; }}
.layout {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; align-items: start; }}
@media (max-width: 1100px) {{ .layout {{ grid-template-columns: 1fr; }} }}
.mono {{ font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }}

/* Topology */
.central {{ width: max-content; margin: 0 auto; background: var(--dark); color: #fff; border-radius: 8px;
  padding: 10px 22px; text-align: center; }}
.central .name {{ font-weight: 700; font-size: 15px; }}
.central .url {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11.5px; opacity: .8; }}
.central .role {{ font-size: 11px; opacity: .65; text-transform: uppercase; letter-spacing: .06em; }}
.link {{ width: 2px; height: 22px; background: var(--dark); margin: 0 auto; }}
.sync {{ border: 2px solid var(--dark); border-radius: 10px; padding: 26px 12px 12px; position: relative; }}
.sync-label {{ position: absolute; top: -11px; left: 50%; transform: translateX(-50%); background: var(--bg);
  padding: 0 10px; font-size: 12px; color: var(--muted); white-space: nowrap; }}
.teams {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(205px, 1fr)); gap: 8px; }}
.team {{ border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; background: var(--soft); min-width: 0; }}
.team .top {{ display: flex; align-items: baseline; gap: 7px; }}
.team .num {{ font-variant-numeric: tabular-nums; font-weight: 700; color: var(--muted); font-size: 12px; }}
.team .name {{ font-weight: 650; font-size: 13.5px; overflow-wrap: anywhere; }}
.team .url {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11px; color: var(--muted); overflow-wrap: anywhere; }}
.team .extra {{ font-size: 11.5px; color: #6d28d9; }}

/* Tables */
table {{ border-collapse: collapse; }}
th, td {{ padding: 3px 8px; text-align: left; }}
thead th {{ border-bottom: 2px solid var(--fg); font-size: 12px; }}
.legend {{ margin-bottom: 20px; width: 100%; }}
.legend td {{ border-bottom: 1px solid var(--line); vertical-align: top; padding-top: 5px; padding-bottom: 5px; }}
.legend .skipped {{ color: #b91c1c; font-size: 12px; }}
.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
.tag {{ display: inline-block; font-size: 11px; font-weight: 700; color: #fff; background: var(--c);
  border-radius: 4px; padding: 1px 6px; }}
.matrix td, .matrix th {{ padding: 1px 4px; }}
.matrix td {{ border-bottom: 1px solid var(--line); font-size: 12.5px; }}
.matrix td:nth-child(2) {{ padding-right: 10px; }}
.matrix tbody tr:nth-child(even) {{ background: var(--soft); }}
.matrix .num {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
.matrix .c {{ text-align: center; }}
.matrix .sub td:nth-child(2) {{ padding-left: 20px; color: #6d28d9; }}
.matrix .central-row td {{ font-weight: 600; }}
.matrices {{ display: flex; gap: 16px; align-items: flex-start; }}
.team .name.unassigned {{ font-style: italic; color: var(--muted); font-weight: 500; }}
.dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: var(--c); }}
.muted {{ color: var(--muted); }}
</style>
</head>
<body>
<div class="page">
  <h1>MISP training environment</h1>
  <div class="sub-title">{len(model["instances"])} team instances · central node {esc(central["org"])} · all URLs use {esc(scheme)}:// · {esc(config_path.name)}</div>
  <div class="layout">
    <section>
      <div class="central"><div class="role">Central node</div><div class="name">{esc(central["org"])}</div>
        <div class="url">{esc(host(central["url"]))}</div></div>
      <div class="link"></div>
      <div class="sync"><div class="sync-label">Every team instance synchronises (push &amp; pull) with the central node</div>
        <div class="teams">{"".join(boxes)}</div></div>
    </section>
    <section>
      <h2>Sharing groups <span class="muted">(central org always included)</span></h2>
      {legend}
      <h2>Membership</h2>
      <div class="matrices">{matrix}</div>
    </section>
  </div>
</div>
</body>
</html>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description='Display the instances and sharing groups defined in a config file.')
    parser.add_argument('-c', '--config', type=Path, default=Path(__file__).resolve().parent / 'generic_config.py',
                        help='Config file to read (default: generic_config.py)')
    parser.add_argument('-o', '--output', type=Path, default=Path('topology.html'),
                        help='Where to write the HTML diagram (default: ./topology.html)')
    parser.add_argument('--table-columns', type=int, default=2,
                        help='Split the membership table in this many side-by-side columns (default: 2)')
    parser.add_argument('--no-open', action='store_true', help='Do not open the diagram in a browser')
    args = parser.parse_args()

    cfg = load_config(args.config)
    model = build_model(cfg)
    check_instance_dirs(cfg, model, args.config.resolve().parent / 'misps')
    print_summary(model)
    args.output.write_text(render_html(model, args.config, max(1, args.table_columns)), encoding='utf-8')
    print(f'\nDiagram written to {args.output.resolve()}')
    if not args.no_open:
        webbrowser.open(args.output.resolve().as_uri())


if __name__ == '__main__':
    main()
