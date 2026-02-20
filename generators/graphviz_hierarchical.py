
"""
Hierarchical GraphViz Generator - Exact Match to Example
Generates the main topology diagram with Organization → Department → Biz_Ownr → Application → MQ Manager
"""

import subprocess
import shutil
from pathlib import Path
from typing import Dict
from datetime import datetime
from utils.common import lighten_color, darken_color
from utils.logging_config import get_logger

logger = get_logger("generators.graphviz_hierarchical")


class HierarchicalGraphVizGenerator:
    """Generate hierarchical MQ topology diagram matching the exact example."""
 
    def __init__(self, data: Dict, config):
        """
        Initialize with enriched hierarchical data.

        Expected structure:
        {
            "Organization Name": {
                "_org_type": "Internal" or "External",
                "_departments": {
                    "Department Name": {
                        "Biz_Ownr Name": {
                            "Application Name": {
                                "MQmanager Name": {...}
                            }
                        }
                    }
                }
            }
        }
        """
        self.data = data
        self.config = config
        self.all_connections = []
        self.mqmgr_lookup = {}
        self.router_qms = []  # Populated during _generate_organizations pre-scan

        # Generate color mapping for departments
        self.department_colors = self._generate_department_color_mapping()
 
    def generate(self) -> str:
        """Generate complete DOT content."""
        sections = [
            self._generate_header(),
            self._generate_organizations(),
            self._generate_connections(),
            self._generate_legend(),
            self._generate_footer(),
            "}"
        ]
        return "\n".join(sections)
 
    def _generate_header(self) -> str:
        """Generate DOT header - exact match."""
        return """digraph MQ_Topology {
    rankdir=LR
    newrank=true
    fontname="Helvetica"
    bgcolor="#f7f9fb"
    splines=curved
    nodesep=0.9
    ranksep=1.5
    /* pack=true
    packmode=cluster */

    node [
        fontname="Helvetica"
        margin="0.35,0.25"
        penwidth=1.2
    ]
    edge [
        fontname="Helvetica"
        fontsize=10
        color="#5d6d7e"
        arrowsize=0.8
    ]
"""
 
    def _sanitize_id(self, name: str) -> str:
        """Sanitize name for GraphViz ID."""
        import re
        sanitized = re.sub(r'[^\w]', '_', name)
        if sanitized and sanitized[0].isdigit():
            sanitized = '_' + sanitized
        return sanitized or 'node'

    def _generate_department_color_mapping(self) -> Dict[str, Dict[str, str]]:
        """Generate unique colors for each department across all organizations."""
        from config.settings import generate_department_colors

        # Collect all unique departments
        all_departments = set()
        for org_name, org_data in self.data.items():
            departments = org_data.get('_departments', {})
            for dept_name in departments.keys():
                all_departments.add(dept_name)

        # Generate color schemes
        num_departments = len(all_departments)
        if num_departments == 0:
            return {}

        color_schemes = generate_department_colors(num_departments)

        # Map department names to colors
        dept_to_color = {}
        for dept_name, color_scheme in zip(sorted(all_departments), color_schemes):
            dept_to_color[dept_name] = color_scheme

        return dept_to_color
 
    def _generate_organizations(self) -> str:
        """Generate all organizations."""
        sections = []

        # Pre-scan: collect router QMs so they can be excluded from org clusters
        # and rendered in the dedicated Router Tier cluster instead
        self.router_qms = []
        for org_data in self.data.values():
            for biz_owners in org_data.get('_departments', {}).values():
                for applications in biz_owners.values():
                    for qm_name, qm_data in applications.get('Router', {}).items():
                        if qm_data.get('IsRouter', False):
                            self.router_qms.append((qm_name, qm_data))

        # Separate external and internal
        external_orgs = []
        internal_orgs = []

        for org_name, org_data in sorted(self.data.items()):
            org_type = org_data.get('_org_type', 'Internal')
            if org_type == 'External':
                external_orgs.append((org_name, org_data))
            else:
                internal_orgs.append((org_name, org_data))

        # External organizations first
        for org_name, org_data in external_orgs:
            sections.append(self._generate_organization(org_name, org_data, 'External'))

        # Router tier between external and internal
        if self.router_qms:
            sections.append(self._generate_routers_cluster())

        # Internal organizations
        for org_name, org_data in internal_orgs:
            sections.append(self._generate_organization(org_name, org_data, 'Internal'))

        return "\n".join(sections)
 
    def _generate_organization(self, org_name: str, org_data: Dict, org_type: str) -> str:
        """Generate a single organization cluster."""
        org_id = self._sanitize_id(org_name)
        departments = org_data.get('_departments', {})
     
        # Choose colors
        if org_type == 'External':
            colors = self.config.EXTERNAL_ORG_COLORS
            title = f"🌐 External Organization: {org_name}"
        else:
            colors = self.config.INTERNAL_ORG_COLORS[0]
            title = f"🏢 Organization: {org_name}"

        # Create gradient fill for organization
        org_bg = colors["org_bg"]
        # Lighten the color slightly for gradient end
        org_bg_light = lighten_color(org_bg, 0.15)

        lines = [
            "",
            f"    /* {'='*26}",
            f"       {org_type.upper()} ORGANIZATION",
            f"    {'='*26} */",
            f"    subgraph cluster_{org_id} {{",
            f'        label=<<b>{title}</b>>',
            f'        style="filled,rounded"',
            f'        fillcolor="{org_bg}:{org_bg_light}"',
            f'        gradientangle=270',
            f'        color="{colors["org_border"]}"',
            f'        penwidth=3',
            f'        fontsize=22' if org_type == 'Internal' else f'        fontsize=20',
            f'        margin=40',
        ]
     
        if org_type == 'Internal':
            lines.append(f'        rankdir=TB')
     
        if org_type == 'External':
            lines.extend([
                "",
                f"        /* Anchor to force this cluster to the top */",
                f"        EXT_ANCHOR [shape=point style=invis width=0 height=0]",
            ])
     
        lines.append("")
     
        # Generate departments
        for dept_name, biz_owners in sorted(departments.items()):
            # Use department-specific colors if available, otherwise use org colors
            dept_colors = self.department_colors.get(dept_name, colors)
            lines.append(self._generate_department(dept_name, biz_owners, dept_colors, org_type))
     
        lines.extend(["    }", ""])
        return "\n".join(lines)
 
    def _generate_department(self, dept_name: str, biz_owners: Dict, colors: Dict, org_type: str) -> str:
        """Generate department cluster."""
        dept_id = self._sanitize_id(dept_name)

        # Create gradient fill for department
        dept_bg = colors["dept_bg"]
        dept_bg_light = lighten_color(dept_bg, 0.12)

        lines = [
            f"        /* {'Department: ' + dept_name} */",
            f'        subgraph cluster_Dep_{dept_id} {{',
            f'            label=<<b>🏬 Department: {dept_name}</b>>',
            f'            style="filled,rounded"',
            f'            fillcolor="{dept_bg}:{dept_bg_light}"',
            f'            gradientangle=270',
            f'            color="{colors["dept_border"]}"',
            f'            penwidth=3' if org_type == 'Internal' else f'            penwidth=2.5',
            f'            fontsize=20',
            f'            margin=25' if org_type == 'Internal' else f'            margin=20',
            ""
        ]
     
        # Generate business owners
        for biz_ownr, applications in sorted(biz_owners.items()):
            lines.append(self._generate_biz_owner(biz_ownr, applications, colors, org_type))
     
        lines.extend(["        }", ""])
        return "\n".join(lines)
 
    def _generate_biz_owner(self, biz_ownr: str, applications: Dict, colors: Dict, org_type: str) -> str:
        """Generate business owner cluster."""
        biz_id = self._sanitize_id(biz_ownr)

        # Create gradient fill for business owner
        biz_bg = colors["biz_bg"]
        biz_bg_light = lighten_color(biz_bg, 0.10)

        lines = [
            f'            /* BIZ OWNER: {biz_ownr} */',
            f'            subgraph cluster_BO_{biz_id} {{',
            f'                label=<<b>👤 Biz_Ownr: {biz_ownr}</b>>',
            f'                style="filled,rounded"',
            f'                fillcolor="{biz_bg}:{biz_bg_light}"',
            f'                gradientangle=270',
            f'                color="{colors["biz_border"]}"',
            f'                penwidth=2.5',
            f'                fontsize=18',
            f'                margin=20' if org_type == 'Internal' else f'                margin=18',
            ""
        ]
     
        # Generate applications
        for app_name, mqmanagers in sorted(applications.items()):
            if app_name == "Router":
                # Router QMs are rendered in the dedicated Router Tier cluster; skip here
                continue
            elif app_name == "No Application":
                # MQ managers without application
                for mqmgr, mq_data in sorted(mqmanagers.items()):
                    lines.append(self._generate_mqmanager_node(mqmgr, mq_data, colors, "                "))
            else:
                lines.append(self._generate_application(app_name, mqmanagers, colors, org_type))
     
        lines.extend(["            }", ""])
        return "\n".join(lines)
 
    def _generate_application(self, app_name: str, mqmanagers: Dict, colors: Dict, org_type: str) -> str:
        """Generate application or gateway cluster."""
        app_id = self._sanitize_id(app_name)

        # Check if this is a gateway
        is_gateway = app_name.startswith("Gateway (")
        if is_gateway:
            # Extract gateway scope (Internal or External)
            scope = app_name.replace("Gateway (", "").replace(")", "")

            # Use gateway-specific colors
            if scope == "Internal":
                gateway_colors = self.config.INTERNAL_GATEWAY_COLORS
            else:
                gateway_colors = self.config.EXTERNAL_GATEWAY_COLORS

            # Create gradient fill for gateway
            gw_bg = gateway_colors["gateway_bg"]
            gw_bg_light = lighten_color(gw_bg, 0.10)

            lines = [
                f'                subgraph cluster_Gateway_{app_id} {{',
                f'                    label=<<b>🔀 Gateway: {scope}</b>>',
                f'                    style="filled,rounded"',
                f'                    fillcolor="{gw_bg}:{gw_bg_light}"',
                f'                    gradientangle=270',
                f'                    color="{gateway_colors["gateway_border"]}"',
                f'                    penwidth=2.5',
                f'                    fontsize=16',
                f'                    margin=15',
                ""
            ]
        else:
            # Regular application cluster - create gradient fill
            app_bg = colors["app_bg"]
            app_bg_light = lighten_color(app_bg, 0.10)

            lines = [
                f'                subgraph cluster_App_{app_id} {{',
                f'                    label=<<b>🧩 App: {app_name}</b>>',
                f'                    style="filled,rounded"',
                f'                    fillcolor="{app_bg}:{app_bg_light}"',
                f'                    gradientangle=270',
                f'                    color="{colors["app_border"]}"',
                f'                    penwidth=2',
                f'                    fontsize=16',
                f'                    margin=15',
            ""
        ]

        # Generate MQ managers
        # Use gateway colors for MQ manager nodes if this is a gateway cluster
        node_colors = gateway_colors if is_gateway else colors
        for mqmgr, mq_data in sorted(mqmanagers.items()):
            lines.append(self._generate_mqmanager_node(mqmgr, mq_data, node_colors, "                    "))

        lines.extend(["                }", ""])
        return "\n".join(lines)
 
    def _generate_routers_cluster(self) -> str:
        """Generate the Router Tier cluster placed between external and internal org clusters."""
        router_colors = self.config.ROUTER_COLORS
        bg = router_colors['cluster_bg']
        bg_light = lighten_color(bg, 0.08)

        lines = [
            "",
            "    /* ==========================",
            "       ROUTER TIER",
            "    ========================== */",
            "    subgraph cluster_ROUTER_TIER {",
            f'        label=<<b>🔀 Router Tier</b>>',
            f'        style="filled,rounded"',
            f'        fillcolor="{bg}:{bg_light}"',
            f'        gradientangle=270',
            f'        color="{router_colors["cluster_border"]}"',
            f'        penwidth=3',
            f'        fontsize=20',
            f'        margin=30',
            "",
            "        /* Invisible anchor for rank-ordering between external and internal tiers */",
            "        ROUTER_TIER_ANCHOR [shape=point style=invis width=0 height=0]",
            "",
        ]

        for qm_name, qm_data in sorted(self.router_qms):
            lines.append(self._generate_router_node(qm_name, qm_data, "        "))

        lines.extend(["    }", ""])
        return "\n".join(lines)

    def _generate_router_node(self, mqmanager: str, mq_data: Dict, indent: str) -> str:
        """Generate a Router QM node with octagon shape and steel-blue styling."""
        router_colors = self.config.ROUTER_COLORS
        qm_id = self._sanitize_id(mqmanager)

        qlocal = mq_data.get('qlocal_count', 0)
        qremote = mq_data.get('qremote_count', 0)
        qalias = mq_data.get('qalias_count', 0)
        inbound = mq_data.get('inbound', [])
        outbound = mq_data.get('outbound', [])
        inbound_extra = mq_data.get('inbound_extra', [])
        outbound_extra = mq_data.get('outbound_extra', [])
        router_desc = mq_data.get('RouterDescription', '')

        # Register in mqmgr_lookup so connection edges can find this node
        self.mqmgr_lookup[mqmanager] = {
            'Organization': mq_data.get('Organization', ''),
            'Department': mq_data.get('Department', ''),
            'Biz_Ownr': mq_data.get('Biz_Ownr', ''),
            'Application': 'Router',
            'Org_Type': mq_data.get('Org_Type', 'Internal')
        }

        # Register outbound connections
        for target in outbound:
            self.all_connections.append({'from': mqmanager, 'to': target})
        for target in outbound_extra:
            self.all_connections.append({'from': mqmanager, 'to': target})

        url_path = f"../individual/{qm_id}.svg"
        node_bg = router_colors['node_bg']
        node_bg_dark = darken_color(node_bg, 0.08)
        desc_line = f"<br/><i>{router_desc}</i>" if router_desc else ""

        return f"""{indent}{qm_id} [
{indent}    shape=octagon
{indent}    style="filled"
{indent}    fillcolor="{node_bg}:{node_bg_dark}"
{indent}    gradientangle=90
{indent}    color="{router_colors['node_border']}"
{indent}    penwidth=2.0
{indent}    fontcolor="{router_colors['node_text']}"
{indent}    URL="{url_path}"
{indent}    target="_blank"
{indent}    tooltip="Click to view {mqmanager} details"
{indent}    label=<<b>🔀 {mqmanager}</b>{desc_line}<br/>QLocal: {qlocal} | QRemote: {qremote} | QAlias: {qalias}<br/> ⬅ In: {len(inbound)}+{len(inbound_extra)} | Out: {len(outbound)}+{len(outbound_extra)} ➡>
{indent}]
"""

    def _generate_mqmanager_node(self, mqmanager: str, mq_data: Dict, colors: Dict, indent: str) -> str:
        """Generate MQ manager node - EXACT format from example."""
        qm_id = self._sanitize_id(mqmanager)
     
        qlocal = mq_data.get('qlocal_count', 0)
        qremote = mq_data.get('qremote_count', 0)
        qalias = mq_data.get('qalias_count', 0)
        inbound = mq_data.get('inbound', [])
        outbound = mq_data.get('outbound', [])
        inbound_extra = mq_data.get('inbound_extra', [])
        outbound_extra = mq_data.get('outbound_extra', [])
        # Include both regular and extra connections in counts
        inbound_count = len(inbound) + len(inbound_extra)
        outbound_count = len(outbound) + len(outbound_extra)
     
        # Store lookup info
        self.mqmgr_lookup[mqmanager] = {
            'Organization': mq_data.get('Organization', ''),
            'Department': mq_data.get('Department', ''),
            'Biz_Ownr': mq_data.get('Biz_Ownr', ''),
            'Application': mq_data.get('Application', ''),
            'Org_Type': mq_data.get('Org_Type', 'Internal')
        }
     
        # Store all connections (both regular and extra)
        for target in outbound:
            self.all_connections.append({'from': mqmanager, 'to': target})
        for target in outbound_extra:
            self.all_connections.append({'from': mqmanager, 'to': target})

        # Build node output
        node_lines = []

        # URL for clickable SVG - links to individual diagram
        # Topology is in diagrams/topology/, individual is in diagrams/individual/
        url_path = f"../individual/{qm_id}.svg"

        # Create gradient fill for MQ manager node (horizontal gradient)
        qm_bg = colors['qm_bg']
        qm_bg_dark = darken_color(qm_bg, 0.08)

        # Main MQ manager node with gradient
        node_lines.append(f"""{indent}{qm_id} [
{indent}    shape=cylinder
{indent}    style="filled"
{indent}    fillcolor="{qm_bg}:{qm_bg_dark}"
{indent}    gradientangle=90
{indent}    color="{colors['qm_border']}"
{indent}    penwidth=1.8
{indent}    fontcolor="{colors['qm_text']}"
{indent}    URL="{url_path}"
{indent}    target="_blank"
{indent}    tooltip="Click to view {mqmanager} details"
{indent}    label=<<b>🗄️ {mqmanager}</b><br/>QLocal: {qlocal} | QRemote: {qremote} | QAlias: {qalias}<br/> ⬅ In: {len(inbound)}+{len(inbound_extra)} | Out: {len(outbound)}+{len(outbound_extra)} ➡>
{indent}]
""")

        # Add note boxes for external connections ONLY for gateways
        is_gateway = mq_data.get('IsGateway', False)

        # Add note box for inbound_extra if present (gateways only)
        # Inbound note positioned on TOP of QM manager with headport=n tailport=s
        if is_gateway and inbound_extra:
            note_id = f"{qm_id}_inbound_extra"
            extra_list = '<br/>'.join([f"• {src}" for src in inbound_extra[:10]])  # Limit to 10
            if len(inbound_extra) > 10:
                extra_list += f"<br/>... and {len(inbound_extra) - 10} more"

            node_lines.append(f"""{indent}{note_id} [
{indent}    shape=note
{indent}    style="filled"
{indent}    fillcolor="#fff3cd"
{indent}    color="#ffc107"
{indent}    penwidth=1.5
{indent}    fontsize=9
{indent}    label=<⬅ <b>External Inbound</b><br/>{extra_list}>
{indent}]
{indent}{note_id} -> {qm_id} [style=dashed color="#999999" arrowhead=none constraint=false headport=n tailport=s]
""")

        # Add note box for outbound_extra if present (gateways only)
        # Outbound note positioned on BOTTOM of QM manager with tailport=s headport=n
        if is_gateway and outbound_extra:
            note_id = f"{qm_id}_outbound_extra"
            extra_list = '<br/>'.join([f"• {tgt}" for tgt in outbound_extra[:10]])  # Limit to 10
            if len(outbound_extra) > 10:
                extra_list += f"<br/>... and {len(outbound_extra) - 10} more"

            node_lines.append(f"""{indent}{note_id} [
{indent}    shape=note
{indent}    style="filled"
{indent}    fillcolor="#d1ecf1"
{indent}    color="#17a2b8"
{indent}    penwidth=1.5
{indent}    fontsize=9
{indent}    label=<➡ <b>External Outbound</b><br/>{extra_list}>
{indent}]
{indent}{qm_id} -> {note_id} [style=dashed color="#999999" arrowhead=none constraint=false tailport=s headport=n]
""")

        return ''.join(node_lines)
 
    def _generate_connections(self) -> str:
        """Generate connections section with bidirectional detection."""
        if not self.all_connections:
            return ""

        # Get connection colors and arrow styles from config
        conn_colors = self.config.CONNECTION_COLORS
        conn_arrows = self.config.CONNECTION_ARROWHEADS
        conn_tails = self.config.CONNECTION_ARROWTAILS

        # Build connection pairs to detect bidirectional
        connection_pairs = {}
        for conn in self.all_connections:
            pair_key = tuple(sorted([conn['from'], conn['to']]))
            if pair_key not in connection_pairs:
                connection_pairs[pair_key] = []
            connection_pairs[pair_key].append(conn)

        # Classify connections
        internal_dept = []
        cross_dept = []
        cross_org_external = []
        bidirectional = []
        processed_pairs = set()

        for conn in self.all_connections:
            from_info = self.mqmgr_lookup.get(conn['from'], {})
            to_info = self.mqmgr_lookup.get(conn['to'], {})

            from_org = from_info.get('Organization', '')
            from_dept = from_info.get('Department', '')
            from_org_type = from_info.get('Org_Type', 'Internal')

            to_org = to_info.get('Organization', '')
            to_dept = to_info.get('Department', '')
            to_org_type = to_info.get('Org_Type', 'Internal')

            # Check if this is a bidirectional connection
            pair_key = tuple(sorted([conn['from'], conn['to']]))
            reverse_exists = any(
                c['from'] == conn['to'] and c['to'] == conn['from']
                for c in connection_pairs[pair_key]
            )

            if reverse_exists and pair_key not in processed_pairs:
                # This is a bidirectional connection - add only once
                bidirectional.append(conn)
                processed_pairs.add(pair_key)
            elif not reverse_exists:
                # Single direction - classify normally
                if from_org_type == 'External' or to_org_type == 'External' or from_org != to_org:
                    cross_org_external.append(conn)
                elif from_dept == to_dept:
                    internal_dept.append(conn)
                else:
                    cross_dept.append(conn)

        lines = [
            "",
            "    /* ==========================",
            "       CONNECTIONS",
            "    ========================== */",
            ""
        ]

        # No explicit ports on connections - let Graphviz find shortest path
        # All edges: pointed arrow at destination, bullet at origin
        if internal_dept:
            lines.append("    /* Internal Department - solid blue */")
            for conn in internal_dept:
                from_id = self._sanitize_id(conn['from'])
                to_id = self._sanitize_id(conn['to'])
                lines.append(f'    {from_id} -> {to_id} [color="{conn_colors["same_dept"]}" penwidth=2.0 dir=both arrowhead={conn_arrows["same_dept"]} arrowtail={conn_tails["same_dept"]} weight=3]')
            lines.append("")

        if cross_dept:
            lines.append("    /* Cross-Department - dashed coral */")
            for conn in cross_dept:
                from_id = self._sanitize_id(conn['from'])
                to_id = self._sanitize_id(conn['to'])
                lines.append(f'    {from_id} -> {to_id} [color="{conn_colors["cross_dept"]}" penwidth=2.2 style=dashed dir=both arrowhead={conn_arrows["cross_dept"]} arrowtail={conn_tails["cross_dept"]} weight=2]')
            lines.append("")

        if cross_org_external:
            lines.append("    /* Cross-Organization / External - dashed purple */")
            for conn in cross_org_external:
                from_id = self._sanitize_id(conn['from'])
                to_id = self._sanitize_id(conn['to'])
                lines.append(f'    {from_id} -> {to_id} [color="{conn_colors["cross_org"]}" penwidth=2.2 style=dashed dir=both arrowhead={conn_arrows["cross_org"]} arrowtail={conn_tails["cross_org"]} weight=1]')
            lines.append("")

        if bidirectional:
            lines.append("    /* Bidirectional - teal, bold, dir=both */")
            for conn in bidirectional:
                from_id = self._sanitize_id(conn['from'])
                to_id = self._sanitize_id(conn['to'])
                lines.append(f'    {from_id} -> {to_id} [color="{conn_colors["bidirectional"]}" penwidth=2.5 style=bold dir=both arrowhead={conn_arrows["bidirectional"]} arrowtail={conn_tails["bidirectional"]} weight=1]')
            lines.append("")

        # Invisible rank-ordering edge: pull Router Tier anchor to the right of External orgs
        if self.router_qms:
            lines.append("    /* Invisible edge: enforce Router Tier between external and internal orgs */")
            lines.append("    EXT_ANCHOR -> ROUTER_TIER_ANCHOR [style=invis weight=100]")
            lines.append("")

        return "\n".join(lines)
 
    def _generate_legend(self) -> str:
        """Generate legend - exact format."""
        return """    /* ==========================
       LEGEND
    ========================== */
    subgraph cluster_legend {
        label=<<b>Legend</b>>
        style="rounded,filled"
        fillcolor="#ffffff"
        color="#d0d8e0"
        penwidth=1.8
        fontsize=14
        margin=20

        legend_item [
            shape=box
            style="rounded,filled"
            fillcolor="#f7f9fb"
            color="#d6d6d6"
            penwidth=1
          label=<
                <table border="0" cellborder="0" cellspacing="4" cellpadding="2">
                    <tr><td align="left"><b>Hierarchy</b></td></tr>
                    <tr><td align="left">🏢 Organization (Internal/External)</td></tr>
                    <tr><td align="left">🏬 Department</td></tr>
                    <tr><td align="left">👤 Biz_Ownr</td></tr>
                    <tr><td align="left">🧩 Application</td></tr>
                    <tr><td align="left">🔀 Gateway (Internal/External)</td></tr>
                    <tr><td align="left">🔀 Router Tier (steel-blue, octagon)</td></tr>
                    <tr><td align="left">🗄️ MQ Manager (clickable)</td></tr>

                    <tr><td><br/></td></tr>

                    <tr><td align="left"><b>MQ Manager Metrics</b></td></tr>
                    <tr><td align="left">QLocal — Local queues</td></tr>
                    <tr><td align="left">QRemote — Remote queues</td></tr>
                    <tr><td align="left">QAlias — Alias queues</td></tr>
                    <tr><td align="left">In: X+Y — Internal+External inbound</td></tr>
                    <tr><td align="left">Out: X+Y — Internal+External outbound</td></tr>

                    <tr><td><br/></td></tr>

                    <tr><td align="left"><b>Connection Types</b></td></tr>
                    <tr><td align="left"><font color="#1f78d1"><b>●────▶ </b></font> Internal (same dept, solid)</td></tr>
                    <tr><td align="left"><font color="#ff6b5a"><b>●- - -▶ </b></font> Cross-department (dashed)</td></tr>
                    <tr><td align="left"><font color="#b455ff"><b>●- - -▶ </b></font> Cross-org / External (dashed)</td></tr>
                    <tr><td align="left"><font color="#00897b"><b>◀━━━▶ </b></font> Bidirectional (bold)</td></tr>

                    <tr><td><br/></td></tr>

                    <tr><td align="left"><b>External Connection Notes</b></td></tr>
                    <tr><td align="left"><font color="#ffc107">📋</font> External Inbound (yellow)</td></tr>
                    <tr><td align="left"><font color="#17a2b8">📋</font> External Outbound (blue)</td></tr>

                </table>
            >
        ]
    }"""

    def _generate_footer(self) -> str:
        """Generate footer with generation timestamp."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"""
    /* ==========================
       FOOTER
    ========================== */
    footer [
        shape=box
        style="rounded,filled"
        fillcolor="#e8e8e8"
        color="#cccccc"
        penwidth=1
        fontsize=10
        label=<<table border="0" cellborder="0" cellspacing="2" cellpadding="2">
            <tr><td align="center"><b>MQ CMDB Topology Diagram</b></td></tr>
            <tr><td align="center"><font point-size="9">Generated: {timestamp}</font></td></tr>
            <tr><td align="center"><font point-size="9">Click on MQ Managers to view details</font></td></tr>
        </table>>
    ]"""
 
    def save_to_file(self, filepath: Path):
        """Save DOT content to file."""
        content = self.generate()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
        logger.info(f"✓ Hierarchical DOT saved: {filepath}")
 
    @staticmethod
    def generate_pdf(dot_file: Path, pdf_file: Path) -> bool:
        """Generate PDF using dot."""
        if not shutil.which('dot'):
            logger.warning("⚠ GraphViz not found - PDF generation skipped")
            logger.info(f"  → Install GraphViz, then run: dot -Tpdf {dot_file} -o {pdf_file}")
            return False
     
        try:
            subprocess.run(['dot', '-Tpdf', str(dot_file), '-o', str(pdf_file)],
                         check=True, capture_output=True)
            logger.info(f"✓ PDF generated: {pdf_file}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ PDF generation failed: {e}")
            return False
