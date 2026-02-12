"""
Individual Application Diagram Generator - WITH FULL HIERARCHY
Shows the application with its full hierarchy, plus connected MQ managers with their hierarchies.
"""

import subprocess
import shutil
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from utils.common import lighten_color, darken_color
from utils.logging_config import get_logger

logger = get_logger("generators.application_diagram")


class ApplicationDiagramGenerator:
    """Generate individual diagrams for each application with full hierarchical context."""

    def __init__(self, enriched_data: Dict, config):
        """
        Initialize generator with enriched hierarchical data.

        Args:
            enriched_data: {Organization: {_org_type: str, _departments: {Department: {Biz_Ownr: {Application: {MQmanager: {...}}}}}}}
            config: Configuration object
        """
        self.enriched_data = enriched_data
        self.config = config

        # Build lookup for quick access to any MQ manager's full context
        self.mqmgr_lookup = self._build_mqmgr_lookup()

        # Initialize external_notes list (populated during diagram generation)
        self.external_notes = []

    def _build_mqmgr_lookup(self) -> Dict:
        """Build a lookup dict: {mqmanager_name: full_context}"""
        lookup = {}
     
        for org_name, org_data in self.enriched_data.items():
            org_type = org_data.get('_org_type', 'Internal')
            departments = org_data.get('_departments', {})
         
            for dept_name, biz_owners in departments.items():
                for biz_ownr, applications in biz_owners.items():
                    for app_name, mqmanagers in applications.items():
                        for mqmgr_name, mq_data in mqmanagers.items():
                            lookup[mqmgr_name] = {
                                'organization': org_name,
                                'org_type': org_type,
                                'department': dept_name,
                                'biz_ownr': biz_ownr,
                                'application': app_name,
                                'data': mq_data
                            }
     
        return lookup
 
    def generate_all(self, output_dir: Path) -> int:
        """Generate diagrams for all applications."""
        output_dir.mkdir(parents=True, exist_ok=True)
     
        # Collect all applications
        applications = self._collect_applications()
     
        logger.info(f"\nGenerating {len(applications)} application diagrams with full hierarchy...")
     
        count = 0
        for app_info in applications:
            app_name = app_info['application']
            safe_name = self._sanitize_filename(app_name)
         
            dot_file = output_dir / f"{safe_name}.dot"
            pdf_file = output_dir / f"{safe_name}.pdf"
         
            # Generate DOT content
            dot_content = self._generate_application_diagram(app_info)
         
            # Save DOT file
            dot_file.write_text(dot_content, encoding='utf-8')
            logger.info(f"  ✓ Generated: {safe_name}.dot")
         
            # Generate PDF if GraphViz available
            if shutil.which('dot'):
                try:
                    subprocess.run(
                        ['dot', '-Tpdf', str(dot_file), '-o', str(pdf_file)],
                        check=True,
                        capture_output=True
                    )
                    logger.info(f"  ✓ Generated: {safe_name}.pdf")
                except subprocess.CalledProcessError:
                    logger.warning(f"PDF generation failed for {safe_name}")
         
            count += 1
     
        return count
 
    def _collect_applications(self) -> List[Dict]:
        """Collect all applications from enriched data."""
        applications = []
     
        for org_name, org_data in self.enriched_data.items():
            org_type = org_data.get('_org_type', 'Internal')
            departments = org_data.get('_departments', {})
         
            for dept_name, biz_owners in departments.items():
                for biz_ownr, apps in biz_owners.items():
                    for app_name, mqmanagers in apps.items():
                        if app_name == "No Application":
                            continue
                     
                        applications.append({
                            'application': app_name,
                            'organization': org_name,
                            'org_type': org_type,
                            'department': dept_name,
                            'biz_ownr': biz_ownr,
                            'mqmanagers': mqmanagers
                        })
     
        return applications
 
    def _generate_application_diagram(self, app_info: Dict) -> str:
        """Generate DOT content for application with full hierarchical context."""
        app_name = app_info['application']
        focus_org = app_info['organization']
        focus_dept = app_info['department']
        focus_biz_ownr = app_info['biz_ownr']
        mqmanagers = app_info['mqmanagers']
     
        # Collect all connected MQ managers and their contexts
        connected_contexts = self._collect_connected_contexts(mqmanagers)
     
        # Build DOT
        lines = [
            f'digraph "{app_name}" {{',
            '    rankdir=TB',
            '    fontname="Helvetica"',
            '    bgcolor="#f7f9fb"',
            '    splines=curved',
            '    nodesep=0.8',
            '    ranksep=1.2',
            '',
            '    node [fontname="Helvetica" margin="0.3,0.2"]',
            '    edge [fontname="Helvetica" fontsize=10 arrowsize=0.8]',
            '',
            f'    labelloc="t"',
            f'    label=<<b><font point-size="20">Application: {app_name}</font></b><br/><font point-size="14">{focus_org} → {focus_dept} → {focus_biz_ownr}</font>>',
            '',
        ]
     
        # Group contexts by organization -> department -> biz_ownr -> application
        hierarchy_map = self._organize_contexts_hierarchically(connected_contexts, focus_org, focus_dept, focus_biz_ownr, app_name)
     
        # Generate hierarchy
        all_connections = []
        self.external_notes = []  # Reset for this diagram
        lines.append(self._generate_hierarchy(hierarchy_map, focus_org, focus_dept, focus_biz_ownr, app_name, all_connections))

        # Generate external connection note boxes (outside all clusters)
        if self.external_notes:
            lines.append("\n    /* External Connection Notes */")
            for note in self.external_notes:
                lines.append(note['box_def'])
                lines.append(note['connection'])

        # Generate connections
        lines.append(self._generate_connections_section(all_connections, focus_org, focus_dept))

        # Generate legend
        lines.append(self._generate_legend(len(mqmanagers), len(connected_contexts)))

        # Generate footer with timestamp
        lines.append(self._generate_footer(app_name))

        lines.append('}')

        return '\n'.join(lines)
 
    def _collect_connected_contexts(self, mqmanagers: Dict) -> Dict:
        """Collect all MQ managers connected to this application's MQ managers."""
        connected = {}
     
        for mqmgr_name, mq_data in mqmanagers.items():
            # Add this MQ manager itself
            if mqmgr_name not in connected:
                connected[mqmgr_name] = self.mqmgr_lookup.get(mqmgr_name, {})
         
            # Add all connected MQ managers
            for target in mq_data.get('outbound', []):
                if target not in connected and target in self.mqmgr_lookup:
                    connected[target] = self.mqmgr_lookup[target]
         
            for source in mq_data.get('inbound', []):
                if source not in connected and source in self.mqmgr_lookup:
                    connected[source] = self.mqmgr_lookup[source]
     
        return connected
 
    def _organize_contexts_hierarchically(self, contexts: Dict, focus_org: str, focus_dept: str,
                                         focus_biz_ownr: str, focus_app: str) -> Dict:
        """Organize contexts into hierarchical structure."""
        hierarchy = {}
     
        for mqmgr_name, context in contexts.items():
            org = context.get('organization', 'Unknown')
            dept = context.get('department', 'Unknown')
            biz_ownr = context.get('biz_ownr', 'Unknown')
            app = context.get('application', 'No Application')
         
            if org not in hierarchy:
                hierarchy[org] = {
                    'org_type': context.get('org_type', 'Internal'),
                    'departments': {}
                }
         
            if dept not in hierarchy[org]['departments']:
                hierarchy[org]['departments'][dept] = {}
         
            if biz_ownr not in hierarchy[org]['departments'][dept]:
                hierarchy[org]['departments'][dept][biz_ownr] = {}
         
            if app not in hierarchy[org]['departments'][dept][biz_ownr]:
                hierarchy[org]['departments'][dept][biz_ownr][app] = {}
         
            hierarchy[org]['departments'][dept][biz_ownr][app][mqmgr_name] = context.get('data', {})
     
        return hierarchy
 
    def _generate_hierarchy(self, hierarchy_map: Dict, focus_org: str, focus_dept: str,
                           focus_biz_ownr: str, focus_app: str, all_connections: List) -> str:
        """Generate the hierarchical structure."""
        lines = []
     
        for org_name, org_data in sorted(hierarchy_map.items()):
            org_type = org_data.get('org_type', 'Internal')
            is_focus_org = (org_name == focus_org)
         
            # Choose colors
            if org_type == 'External':
                colors = self.config.EXTERNAL_ORG_COLORS
            else:
                colors = self.config.INTERNAL_ORG_COLORS[0]
         
            org_id = self._sanitize_id(org_name)

            # Create gradient fill for organization
            org_bg = colors["org_bg"]
            org_bg_light = lighten_color(org_bg, 0.15)

            lines.extend([
                f'    subgraph cluster_{org_id} {{',
                f'        label=<<b>🏢 Organization: {org_name}</b>>',
                f'        style="filled,rounded"',
                f'        fillcolor="{org_bg}:{org_bg_light}"',
                f'        gradientangle=270',
                f'        color="{colors["org_border"]}"',
                f'        penwidth=3',
                f'        fontsize=18',
                ''
            ])
         
            for dept_name, biz_owners in sorted(org_data['departments'].items()):
                is_focus_dept = (is_focus_org and dept_name == focus_dept)
                dept_id = self._sanitize_id(dept_name)

                # Create gradient fill for department
                dept_bg = colors["dept_bg"]
                dept_bg_light = lighten_color(dept_bg, 0.12)

                lines.extend([
                    f'        subgraph cluster_Dep_{dept_id} {{',
                    f'            label=<<b>🏬 Department: {dept_name}</b>>',
                    f'            style="filled,rounded"',
                    f'            fillcolor="{dept_bg}:{dept_bg_light}"',
                    f'            gradientangle=270',
                    f'            color="{colors["dept_border"]}"',
                    f'            penwidth=2.5',
                    ''
                ])
             
                for biz_ownr, applications in sorted(biz_owners.items()):
                    is_focus_biz = (is_focus_dept and biz_ownr == focus_biz_ownr)
                    biz_id = self._sanitize_id(biz_ownr)

                    # Create gradient fill for business owner
                    biz_bg = colors["biz_bg"]
                    biz_bg_light = lighten_color(biz_bg, 0.10)

                    lines.extend([
                        f'            subgraph cluster_BO_{biz_id} {{',
                        f'                label=<<b>👤 Biz_Ownr: {biz_ownr}</b>>',
                        f'                style="filled,rounded"',
                        f'                fillcolor="{biz_bg}:{biz_bg_light}"',
                        f'                gradientangle=270',
                        f'                color="{colors["biz_border"]}"',
                        f'                penwidth=2',
                        ''
                    ])
                 
                    for app_name, mqmanagers in sorted(applications.items()):
                        is_focus_app = (is_focus_biz and app_name == focus_app)
                        app_id = self._sanitize_id(app_name)

                        # Check if this is a gateway
                        is_gateway = app_name.startswith("Gateway (")

                        if is_gateway:
                            # Extract gateway scope
                            scope = app_name.replace("Gateway (", "").replace(")", "")

                            # Use gateway-specific colors
                            if scope == "Internal":
                                gateway_colors = self.config.INTERNAL_GATEWAY_COLORS
                            else:
                                gateway_colors = self.config.EXTERNAL_GATEWAY_COLORS

                            # Highlight focus gateway if applicable
                            if is_focus_app:
                                app_fillcolor = "#fffacd"  # Light yellow highlight
                                app_fillcolor_light = "#fffff0"
                                app_border = "#ffa500"
                                penwidth = "3"
                            else:
                                app_fillcolor = gateway_colors["gateway_bg"]
                                app_fillcolor_light = lighten_color(app_fillcolor, 0.10)
                                app_border = gateway_colors["gateway_border"]
                                penwidth = "2.5"

                            lines.extend([
                                f'                subgraph cluster_Gateway_{app_id} {{',
                                f'                    label=<<b>🔀 Gateway: {scope}</b>>',
                                f'                    style="filled,rounded"',
                                f'                    fillcolor="{app_fillcolor}:{app_fillcolor_light}"',
                                f'                    gradientangle=270',
                                f'                    color="{app_border}"',
                                f'                    penwidth={penwidth}',
                                ''
                            ])
                        else:
                            # Highlight focus application
                            if is_focus_app:
                                app_fillcolor = "#fffacd"  # Light yellow highlight
                                app_fillcolor_light = "#fffff0"
                                app_border = "#ffa500"
                                penwidth = "3"
                            else:
                                app_fillcolor = colors["app_bg"]
                                app_fillcolor_light = lighten_color(app_fillcolor, 0.10)
                                app_border = colors["app_border"]
                                penwidth = "2"

                            lines.extend([
                                f'                subgraph cluster_App_{app_id} {{',
                                f'                    label=<<b>🧩 App: {app_name}</b>>',
                                f'                    style="filled,rounded"',
                                f'                    fillcolor="{app_fillcolor}:{app_fillcolor_light}"',
                                f'                    gradientangle=270',
                                f'                    color="{app_border}"',
                                f'                    penwidth={penwidth}',
                                ''
                            ])
                     
                        # Use gateway colors for MQ manager nodes if this is a gateway cluster
                        node_colors = gateway_colors if is_gateway else colors
                        for mqmgr_name, mq_data in sorted(mqmanagers.items()):
                            lines.append(self._generate_mqmanager_node(
                                mqmgr_name, mq_data, node_colors, is_focus_app,
                                "                    ", all_connections
                            ))

                        lines.extend(['                }', ''])
                 
                    lines.extend(['            }', ''])
             
                lines.extend(['        }', ''])
         
            lines.extend(['    }', ''])
     
        return '\n'.join(lines)
 
    def _generate_mqmanager_node(self, mqmgr_name: str, mq_data: Dict, colors: Dict,
                                 is_focus: bool, indent: str, all_connections: List) -> str:
        """Generate MQ manager node."""
        qm_id = self._sanitize_id(mqmgr_name)
     
        qlocal = mq_data.get('qlocal_count', 0)
        qremote = mq_data.get('qremote_count', 0)
        qalias = mq_data.get('qalias_count', 0)
        inbound = mq_data.get('inbound', [])
        outbound = mq_data.get('outbound', [])
        inbound_extra = mq_data.get('inbound_extra', [])
        outbound_extra = mq_data.get('outbound_extra', [])

        # Store connections
        # Regular connections are always added
        for target in outbound:
            all_connections.append({
                'from': mqmgr_name,
                'to': target,
                'is_focus_source': is_focus,
                'type': 'outbound'
            })

        for source in inbound:
            all_connections.append({
                'from': source,
                'to': mqmgr_name,
                'is_focus_source': False,
                'type': 'inbound'
            })

        # For FOCUSED MQ managers: Don't add individual external connections
        # (they're shown in note boxes instead)
        # For non-focused: Add external connections normally
        if not is_focus:
            for target in outbound_extra:
                all_connections.append({
                    'from': mqmgr_name,
                    'to': target,
                    'is_focus_source': is_focus,
                    'type': 'outbound_extra'
                })

            for source in inbound_extra:
                all_connections.append({
                    'from': source,
                    'to': mqmgr_name,
                    'is_focus_source': False,
                    'type': 'inbound_extra'
                })

        # Highlight focus MQ managers
        if is_focus:
            fillcolor = "#ffeb3b"
            fillcolor_dark = "#ffd700"
            bordercolor = "#ff9800"
        else:
            fillcolor = colors['qm_bg']
            fillcolor_dark = darken_color(fillcolor, 0.08)
            bordercolor = colors['qm_border']

        # Build node output
        node_lines = []

        # URL for clickable SVG - links to individual diagram
        # Applications is in diagrams/applications/, individual is in diagrams/individual/
        url_path = f"../individual/{qm_id}.svg"

        # Main MQ manager node with gradient fill
        node_lines.append(f"""{indent}{qm_id} [
{indent}    shape=cylinder
{indent}    style="filled"
{indent}    fillcolor="{fillcolor}:{fillcolor_dark}"
{indent}    gradientangle=90
{indent}    color="{bordercolor}"
{indent}    penwidth=1.8
{indent}    fontcolor="#000000"
{indent}    URL="{url_path}"
{indent}    target="_blank"
{indent}    tooltip="Click to view {mqmgr_name} details"
{indent}    label=<<b>🗄️ {mqmgr_name}</b><br/>QLocal: {qlocal} | QRemote: {qremote} | QAlias: {qalias}<br/>⬅ In: {len(inbound)}+{len(inbound_extra)} | Out: {len(outbound)}+{len(outbound_extra)} ➡>
{indent}]
""")

        # Store external connection note boxes for focused MQ managers (render outside clusters)
        # Inbound note positioned on TOP with headport=n tailport=s
        if is_focus and inbound_extra:
            note_id = f"{qm_id}_inbound_extra"
            extra_list = '<br/>'.join([f"• {src}" for src in inbound_extra[:10]])
            if len(inbound_extra) > 10:
                extra_list += f"<br/>... and {len(inbound_extra) - 10} more"

            # Store note box to render outside all clusters
            box_def = f"""    {note_id} [
        shape=note
        style="filled"
        fillcolor="#fff3cd"
        color="#ffc107"
        penwidth=1.5
        fontsize=9
        label=<⬅ <b>External Inbound</b><br/>{extra_list}>
    ]"""

            # Connection FROM note box TO the MQ manager (top position)
            connection = f"    {note_id} -> {qm_id} [style=dashed color=\"#ffc107\" penwidth=2 constraint=false headport=n tailport=s]"

            self.external_notes.append({'box_def': box_def, 'connection': connection})

        # Outbound note positioned on BOTTOM with tailport=s headport=n
        if is_focus and outbound_extra:
            note_id = f"{qm_id}_outbound_extra"
            extra_list = '<br/>'.join([f"• {tgt}" for tgt in outbound_extra[:10]])
            if len(outbound_extra) > 10:
                extra_list += f"<br/>... and {len(outbound_extra) - 10} more"

            # Store note box to render outside all clusters
            box_def = f"""    {note_id} [
        shape=note
        style="filled"
        fillcolor="#d1ecf1"
        color="#17a2b8"
        penwidth=1.5
        fontsize=9
        label=<➡ <b>External Outbound</b><br/>{extra_list}>
    ]"""

            # Connection FROM the MQ manager TO note box (bottom position)
            connection = f"    {qm_id} -> {note_id} [style=dashed color=\"#17a2b8\" penwidth=2 constraint=false tailport=s headport=n]"

            self.external_notes.append({'box_def': box_def, 'connection': connection})

        return ''.join(node_lines)
 
    def _generate_connections_section(self, connections: List, focus_org: str, focus_dept: str) -> str:
        """
        Generate connections with classification and bidirectional detection.
        Only shows:
        1. Direct connections FROM focus application MQ managers TO targets
        2. Reverse connections FROM those targets BACK TO focus application MQ managers
        3. Bidirectional connections shown with teal color and dir=both

        Does NOT show connections between non-focus MQ managers.
        """
        if not connections:
            return ""

        # Get connection colors and arrow styles from config
        conn_colors = self.config.CONNECTION_COLORS
        conn_arrows = self.config.CONNECTION_ARROWHEADS
        conn_tails = self.config.CONNECTION_ARROWTAILS

        # Get focus application MQ managers
        focus_mqmgrs = set()
        for conn in connections:
            if conn.get('is_focus_source'):
                focus_mqmgrs.add(conn['from'])

        # Build connection pairs to detect bidirectional
        connection_pairs = {}
        for conn in connections:
            pair_key = tuple(sorted([conn['from'], conn['to']]))
            if pair_key not in connection_pairs:
                connection_pairs[pair_key] = []
            connection_pairs[pair_key].append(conn)

        # Filter connections:
        # 1. Direct: focus -> target
        # 2. Reverse: target -> focus (if target was in direct connections)
        # 3. Bidirectional: both directions exist
        direct_connections = []
        reverse_connections = []
        bidirectional_connections = []
        seen_pairs = set()
        processed_bidirectional = set()

        for conn in connections:
            from_mqmgr = conn['from']
            to_mqmgr = conn['to']
            pair_key = tuple(sorted([from_mqmgr, to_mqmgr]))

            # Check if this is a bidirectional connection
            reverse_exists = any(
                c['from'] == to_mqmgr and c['to'] == from_mqmgr
                for c in connection_pairs.get(pair_key, [])
            )

            if reverse_exists and pair_key not in processed_bidirectional:
                # This is a bidirectional connection - add only once
                if from_mqmgr in focus_mqmgrs or to_mqmgr in focus_mqmgrs:
                    bidirectional_connections.append(conn)
                    processed_bidirectional.add(pair_key)
            elif not reverse_exists:
                # Single direction - classify normally
                pair = (from_mqmgr, to_mqmgr)

                # Direct connection: from focus MQ manager to any target
                if from_mqmgr in focus_mqmgrs:
                    if pair not in seen_pairs:
                        direct_connections.append(conn)
                        seen_pairs.add(pair)

                # Reverse connection: from target back to focus MQ manager
                elif to_mqmgr in focus_mqmgrs and from_mqmgr not in focus_mqmgrs:
                    if pair not in seen_pairs:
                        reverse_connections.append(conn)
                        seen_pairs.add(pair)

        lines = ['', '    /* Connections */', '']

        # Draw direct connections (focus -> target) - no explicit ports for shortest path
        if direct_connections:
            lines.append('    /* Direct connections from focus application */')
            for conn in direct_connections:
                from_id = self._sanitize_id(conn['from'])
                to_id = self._sanitize_id(conn['to'])

                from_context = self.mqmgr_lookup.get(conn['from'], {})
                to_context = self.mqmgr_lookup.get(conn['to'], {})

                from_org = from_context.get('organization', '')
                from_dept = from_context.get('department', '')
                to_org = to_context.get('organization', '')
                to_dept = to_context.get('department', '')

                # Classify connection with config colors and arrowheads
                # All edges: pointed arrow at destination, bullet at origin
                if from_org != to_org:
                    color = conn_colors["cross_org"]
                    style = "dashed"
                    penwidth = "2.5"
                    arrowhead = conn_arrows["cross_org"]
                    arrowtail = conn_tails["cross_org"]
                elif from_dept != to_dept:
                    color = conn_colors["cross_dept"]
                    style = "dashed"
                    penwidth = "2.2"
                    arrowhead = conn_arrows["cross_dept"]
                    arrowtail = conn_tails["cross_dept"]
                else:
                    color = conn_colors["same_dept"]
                    style = "solid"
                    penwidth = "2.0"
                    arrowhead = conn_arrows["same_dept"]
                    arrowtail = conn_tails["same_dept"]

                lines.append(f'    {from_id} -> {to_id} [color="{color}" penwidth={penwidth} style={style} dir=both arrowhead={arrowhead} arrowtail={arrowtail}]')
            lines.append('')

        # Draw bidirectional connections with teal color
        if bidirectional_connections:
            lines.append('    /* Bidirectional connections - teal */')
            for conn in bidirectional_connections:
                from_id = self._sanitize_id(conn['from'])
                to_id = self._sanitize_id(conn['to'])
                lines.append(f'    {from_id} -> {to_id} [color="{conn_colors["bidirectional"]}" penwidth=2.5 style=bold dir=both arrowhead={conn_arrows["bidirectional"]} arrowtail={conn_tails["bidirectional"]}]')
            lines.append('')

        # Draw reverse connections (target -> focus) in green
        if reverse_connections:
            lines.append('    /* Reverse connections to focus application */')
            for conn in reverse_connections:
                from_id = self._sanitize_id(conn['from'])
                to_id = self._sanitize_id(conn['to'])

                # Reverse connections in green - arrow points TO focus, bullet at origin
                lines.append(f'    {from_id} -> {to_id} [color="{conn_colors["reverse"]}" penwidth=2.0 style=dashed dir=both arrowhead=normal arrowtail=dot]')
            lines.append('')

        return '\n'.join(lines)
 
    def _generate_legend(self, focus_count: int, total_count: int) -> str:
        """Generate legend."""
        return f"""
    /* Legend */
    subgraph cluster_legend {{
        label="Legend"
        style="rounded,filled"
        fillcolor="#ffffff"
        color="#d0d8e0"
        penwidth=1.5
        fontsize=12

        legend [
            shape=box
            style="rounded,filled"
            fillcolor="#f7f9fb"
            label=<
                <table border="0" cellborder="0" cellspacing="2" cellpadding="4">
                    <tr><td align="left"><b>Focus Application</b></td></tr>
                    <tr><td bgcolor="#fffacd" align="left">  Highlighted in yellow</td></tr>
                    <tr><td align="left">  MQ Managers: {focus_count} (clickable)</td></tr>
                    <tr><td><br/></td></tr>
                    <tr><td align="left"><b>Connected MQ Managers</b></td></tr>
                    <tr><td align="left">  Total shown: {total_count}</td></tr>
                    <tr><td><br/></td></tr>
                    <tr><td align="left"><b>MQ Manager Metrics</b></td></tr>
                    <tr><td align="left">  In: X+Y — Internal+External inbound</td></tr>
                    <tr><td align="left">  Out: X+Y — Internal+External outbound</td></tr>
                    <tr><td><br/></td></tr>
                    <tr><td align="left"><b>Direct Connections (from focus)</b></td></tr>
                    <tr><td align="left"><font color="#1f78d1">●────▶ </font> Same department (solid)</td></tr>
                    <tr><td align="left"><font color="#ff6b5a">●- - -▶ </font> Cross-department (dashed)</td></tr>
                    <tr><td align="left"><font color="#b455ff">●- - -▶ </font> Cross-organization (dashed)</td></tr>
                    <tr><td><br/></td></tr>
                    <tr><td align="left"><b>Bidirectional Connections</b></td></tr>
                    <tr><td align="left"><font color="#00897b"><b>◀━━━▶</b></font> Two-way communication (bold)</td></tr>
                    <tr><td><br/></td></tr>
                    <tr><td align="left"><b>Reverse Connections (to focus)</b></td></tr>
                    <tr><td align="left"><font color="#28a745">●- - -▶ </font> From external sources (dashed)</td></tr>
                    <tr><td><br/></td></tr>
                    <tr><td align="left"><b>External Connection Notes</b></td></tr>
                    <tr><td align="left"><font color="#ffc107">📋</font> External Inbound (yellow)</td></tr>
                    <tr><td align="left"><font color="#17a2b8">📋</font> External Outbound (blue)</td></tr>
                </table>
            >
        ]
    }}"""

    def _generate_footer(self, app_name: str) -> str:
        """Generate footer with generation timestamp."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"""
    /* Footer */
    footer [
        shape=box
        style="rounded,filled"
        fillcolor="#e8e8e8"
        color="#cccccc"
        penwidth=1
        fontsize=10
        label=<<table border="0" cellborder="0" cellspacing="2" cellpadding="2">
            <tr><td align="center"><b>Application Diagram: {app_name}</b></td></tr>
            <tr><td align="center"><font point-size="9">Generated: {timestamp}</font></td></tr>
            <tr><td align="center"><font point-size="9">Click on MQ Managers to view details</font></td></tr>
        </table>>
    ]"""
 
    def _sanitize_id(self, name: str) -> str:
        """Sanitize name for GraphViz ID."""
        import re
        sanitized = re.sub(r'[^\w]', '_', name)
        if sanitized and sanitized[0].isdigit():
            sanitized = '_' + sanitized
        return sanitized or 'node'
 
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize application name for filename."""
        import re
        sanitized = re.sub(r'[^\w\s-]', '_', name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        sanitized = re.sub(r'_+', '_', sanitized)
        result = sanitized.strip('_').lower()
        return result if result else 'unnamed_app'
