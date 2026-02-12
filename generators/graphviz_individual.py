"""Individual MQ Manager diagram generator."""

from typing import Dict
from pathlib import Path
from datetime import datetime
from utils.common import lighten_color


class IndividualDiagramGenerator:
    """Generate focused diagrams for individual MQ Managers."""

    def __init__(self, data: Dict, config):
        self.data = data
        self.config = config

    def generate_diagram(self, mqmanager: str, directorate: str, info: Dict) -> str:
        """Generate diagram for single MQ Manager."""
        from utils.common import sanitize_id
     
        qm_id = sanitize_id(mqmanager)
        colors = self.config.INDIVIDUAL_DIAGRAM_COLORS
     
        sections = [
            self._header(mqmanager, directorate),
            self._central_node(mqmanager, directorate, info, qm_id, colors),
            self._inbound_nodes(info, qm_id, colors),
            self._outbound_nodes(info, qm_id, colors),
            self._external_nodes(info, qm_id, colors),
            self._legend(colors),
            self._footer(mqmanager),
            "}"
        ]
        return "\n".join(filter(None, sections))
 
    def _header(self, mqmanager: str, directorate: str) -> str:
        """Generate header."""
        from utils.common import sanitize_id
     
        return f"""digraph MQ_{sanitize_id(mqmanager)} {{
    rankdir=LR fontname="Helvetica" bgcolor="{self.config.GRAPHVIZ_BGCOLOR}"
    splines=curved nodesep=0.6 ranksep=1.0

    labelloc="t"
    label=<<b>MQ Manager: {mqmanager}</b><br/><font point-size='11'>Directorate: {directorate}</font>>
    fontsize=18

    node [fontname="Helvetica" margin="0.40,0.25" penwidth=1.2]
    edge [fontname="Helvetica" fontsize=9 arrowsize=0.7]
"""
 
    def _central_node(self, mqmanager: str, directorate: str, info: Dict, qm_id: str, colors: Dict) -> str:
        """Generate central node with gradient fill."""
        central = colors["central"]
        inbound_count = len(info.get('inbound', []))
        outbound_count = len(info.get('outbound', []))
        inbound_extra_count = len(info.get('inbound_extra', []))
        outbound_extra_count = len(info.get('outbound_extra', []))

        # Create gradient fill for central node
        fill_light = lighten_color(central['fill'], 0.2)

        return f"""    {qm_id} [
        shape=cylinder style="filled"
        fillcolor="{central['fill']}:{fill_light}" gradientangle=90
        color="{central['border']}" penwidth=3.0
        fontcolor="{central['text']}"
        label=<
            <table border="0" cellborder="0" cellspacing="0" cellpadding="4">
                <tr><td align="center"><b><font point-size='16'>🗄️ {mqmanager}</font></b></td></tr>
                <tr><td align="center"><font point-size="10"><b>Directorate: {directorate}</b></font></td></tr>
                <tr><td><br/></td></tr>
                <tr><td align="center"><b>Queue Statistics</b></td></tr>
                <tr><td align="center"><font point-size="10">QLocal: {info.get('qlocal_count', 0)} | QRemote: {info.get('qremote_count', 0)} | QAlias: {info.get('qalias_count', 0)}</font></td></tr>
                <tr><td><br/></td></tr>
                <tr><td align="center"><b>Connections</b></td></tr>
                <tr><td align="center"><font point-size="10">⬅ Inbound: {inbound_count}+{inbound_extra_count} | Outbound: {outbound_count}+{outbound_extra_count} ➡</font></td></tr>
            </table>
        >
    ]
"""
 
    def _inbound_nodes(self, info: Dict, qm_id: str, colors: Dict) -> str:
        """Generate inbound nodes with gradient fills and bidirectional detection."""
        from utils.common import sanitize_id

        inbound_list = info.get('inbound', [])
        outbound_list = info.get('outbound', [])
        if not inbound_list:
            return ""

        lines = ["    /* Inbound MQ Managers */"]
        inbound = colors["inbound"]
        conn_colors = self.config.CONNECTION_COLORS

        # Create gradient fill for inbound nodes
        fill_light = lighten_color(inbound['fill'], 0.15)

        for inbound_mgr in inbound_list:
            inbound_id = sanitize_id(inbound_mgr)
            inbound_dir = self._find_directorate(inbound_mgr)
            url_path = f"{inbound_id}.svg"

            # Check if this is a bidirectional connection
            is_bidirectional = inbound_mgr in outbound_list

            lines.extend([
                f"    {inbound_id} [shape=cylinder style=\"filled\" fillcolor=\"{inbound['fill']}:{fill_light}\" gradientangle=90",
                f"        color=\"{inbound['border']}\" penwidth=1.5",
                f"        URL=\"{url_path}\" target=\"_blank\" tooltip=\"Click to view {inbound_mgr} details\"",
                f"        label=<<b>{inbound_mgr}</b><br/><font point-size='8'>{inbound_dir}</font>>]",
            ])

            # Use teal for bidirectional, normal color for unidirectional
            # All edges: pointed arrow at destination, bullet at origin
            if is_bidirectional:
                lines.append(f"    {inbound_id} -> {qm_id} [color=\"{conn_colors['bidirectional']}\" penwidth=2.5 style=bold dir=both arrowhead=normal arrowtail=dot label=\"bidirectional\"]")
            else:
                lines.append(f"    {inbound_id} -> {qm_id} [color=\"{inbound['arrow']}\" penwidth=2.0 dir=both arrowhead=normal arrowtail=dot label=\"sends to\"]")

        return "\n".join(lines) + "\n"
 
    def _outbound_nodes(self, info: Dict, qm_id: str, colors: Dict) -> str:
        """Generate outbound nodes with gradient fills, skip bidirectional (handled in inbound)."""
        from utils.common import sanitize_id

        outbound_list = info.get('outbound', [])
        inbound_list = info.get('inbound', [])
        if not outbound_list:
            return ""

        lines = ["    /* Outbound MQ Managers */"]
        outbound = colors["outbound"]

        # Create gradient fill for outbound nodes
        fill_light = lighten_color(outbound['fill'], 0.15)

        for outbound_mgr in outbound_list:
            # Skip if this is a bidirectional connection (already handled in inbound)
            if outbound_mgr in inbound_list:
                continue

            outbound_id = sanitize_id(outbound_mgr)
            outbound_dir = self._find_directorate(outbound_mgr)
            url_path = f"{outbound_id}.svg"
            lines.extend([
                f"    {outbound_id} [shape=cylinder style=\"filled\" fillcolor=\"{outbound['fill']}:{fill_light}\" gradientangle=90",
                f"        color=\"{outbound['border']}\" penwidth=1.5",
                f"        URL=\"{url_path}\" target=\"_blank\" tooltip=\"Click to view {outbound_mgr} details\"",
                f"        label=<<b>{outbound_mgr}</b><br/><font point-size='8'>{outbound_dir}</font>>]",
                f"    {qm_id} -> {outbound_id} [color=\"{outbound['arrow']}\" penwidth=2.0 dir=both arrowhead=normal arrowtail=dot label=\"sends to\"]"
            ])

        return "\n".join(lines) + "\n"
 
    def _external_nodes(self, info: Dict, qm_id: str, colors: Dict) -> str:
        """Generate external system nodes with gradient fills and proper positioning."""
        from utils.common import sanitize_id

        inbound_extra = info.get('inbound_extra', [])
        outbound_extra = info.get('outbound_extra', [])

        if not inbound_extra and not outbound_extra:
            return ""

        lines = []
        external = colors["external"]

        # Create gradient fill for external nodes
        fill_light = lighten_color(external["fill"], 0.12)

        # External inbound - positioned on TOP with headport=n tailport=s
        # All edges: pointed arrow at destination, bullet at origin
        if inbound_extra:
            lines.append("    /* External Inbound (top) */")
            for idx, ext in enumerate(inbound_extra):
                ext_id = f"ext_in_{idx}_{sanitize_id(ext[:20])}"
                lines.extend([
                    f'    {ext_id} [shape=box style="rounded,filled,dashed" fillcolor="{external["fill"]}:{fill_light}" gradientangle=270 color="{external["border"]}" label="{ext}" fontsize=9]',
                    f'    {ext_id} -> {qm_id} [color="{external["arrow"]}" style=dashed dir=both arrowhead=normal arrowtail=dot label="external" constraint=false headport=n tailport=s]'
                ])

        # External outbound - positioned on BOTTOM with tailport=s headport=n
        if outbound_extra:
            lines.append("    /* External Outbound (bottom) */")
            for idx, ext in enumerate(outbound_extra):
                ext_id = f"ext_out_{idx}_{sanitize_id(ext[:20])}"
                lines.extend([
                    f'    {ext_id} [shape=box style="rounded,filled,dashed" fillcolor="{external["fill"]}:{fill_light}" gradientangle=270 color="{external["border"]}" label="{ext}" fontsize=9]',
                    f'    {qm_id} -> {ext_id} [color="{external["arrow"]}" style=dashed dir=both arrowhead=normal arrowtail=dot label="external" constraint=false tailport=s headport=n]'
                ])

        return "\n".join(lines) + "\n"
 
    def _legend(self, colors: Dict) -> str:
        """Generate legend."""
        conn_colors = self.config.CONNECTION_COLORS
        return f"""    subgraph cluster_legend {{
        label="Legend" style="rounded,filled" fillcolor="#ffffff" color="#d0d8e0" fontsize=11 margin=15

        legend_item [shape=box style="rounded,filled" fillcolor="#f7f9fb"
            label=<
                <table border="0" cellborder="0" cellspacing="3" cellpadding="2">
                    <tr><td align="left"><font color="{colors['central']['border']}">🗄️</font> <b>This MQ Manager</b></td></tr>
                    <tr><td align="left"><font color="{colors['inbound']['arrow']}">🗄️</font> Inbound Sources (clickable)</td></tr>
                    <tr><td align="left"><font color="{colors['outbound']['arrow']}">🗄️</font> Outbound Targets (clickable)</td></tr>
                    <tr><td align="left"><font color="{colors['external']['arrow']}">⬜</font> External Systems</td></tr>
                    <tr><td><br/></td></tr>
                    <tr><td align="left"><b>Connection Types</b></td></tr>
                    <tr><td align="left"><font color="{colors['inbound']['arrow']}">●────▶</font> Inbound (solid)</td></tr>
                    <tr><td align="left"><font color="{colors['outbound']['arrow']}">●────▶</font> Outbound (solid)</td></tr>
                    <tr><td align="left"><font color="{conn_colors['bidirectional']}"><b>◀━━━▶</b></font> Bidirectional (bold)</td></tr>
                    <tr><td align="left"><font color="{colors['external']['arrow']}">●- - -▶</font> External (dashed)</td></tr>
                    <tr><td><br/></td></tr>
                    <tr><td align="left"><b>Connection Metrics</b></td></tr>
                    <tr><td align="left">  In: X+Y — Internal+External inbound</td></tr>
                    <tr><td align="left">  Out: X+Y — Internal+External outbound</td></tr>
                </table>
            >
        ]
    }}"""

    def _footer(self, mqmanager: str) -> str:
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
            <tr><td align="center"><b>MQ Manager: {mqmanager}</b></td></tr>
            <tr><td align="center"><font point-size="9">Generated: {timestamp}</font></td></tr>
            <tr><td align="center"><font point-size="9">Click on connected MQ Managers to navigate</font></td></tr>
        </table>>
    ]"""
 
    def _find_directorate(self, mqmanager: str) -> str:
        """Find directorate for MQmanager."""
        for directorate, mqmanagers in self.data.items():
            if mqmanager in mqmanagers:
                return directorate
        return "Unknown"
 
    def generate_all(self, output_dir: Path) -> int:
        """Generate all individual diagrams."""
        from utils.common import sanitize_id
        from generators.graphviz_topology import GraphVizTopologyGenerator

        output_dir.mkdir(parents=True, exist_ok=True)
        count = 0

        for directorate, mqmanagers in self.data.items():
            for mqmanager, info in mqmanagers.items():
                dot_content = self.generate_diagram(mqmanager, directorate, info)
                safe_name = sanitize_id(mqmanager)
                dot_file = output_dir / f"{safe_name}.dot"
                pdf_file = output_dir / f"{safe_name}.pdf"

                dot_file.write_text(dot_content, encoding='utf-8')
                GraphVizTopologyGenerator.generate_pdf(dot_file, pdf_file)
                count += 1

        return count

