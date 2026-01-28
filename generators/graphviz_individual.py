"""Individual MQ Manager diagram generator."""

from typing import Dict
from pathlib import Path

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
        """Generate central node."""
        central = colors["central"]
        return f"""    {qm_id} [
        shape=cylinder style="filled"
        fillcolor="{central['fill']}" color="{central['border']}" penwidth=3.0
        fontcolor="{central['text']}"
        label=<
            <table border="0" cellborder="0" cellspacing="0" cellpadding="4">
                <tr><td align="center"><b><font point-size='14'>🗄️ {mqmanager}</font></b></td></tr>
                <tr><td align="center"><font point-size="10">Directorate: {directorate}</font></td></tr>
                <tr><td><br/></td></tr>
                <tr><td align="center"><b>Queue Statistics</b></td></tr>
                <tr><td align="center"><font point-size="10">QLocal: {info.get('qlocal_count', 0)} | QRemote: {info.get('qremote_count', 0)} | QAlias: {info.get('qalias_count', 0)}</font></td></tr>
                <tr><td><br/></td></tr>
                <tr><td align="center"><b>Connections</b></td></tr>
                <tr><td align="center"><font point-size="10">⬅ Inbound: {len(info.get('inbound', []))} | Outbound: {len(info.get('outbound', []))} ➡</font></td></tr>
            </table>
        >
    ]
"""
   
    def _inbound_nodes(self, info: Dict, qm_id: str, colors: Dict) -> str:
        """Generate inbound nodes."""
        from utils.common import sanitize_id
       
        inbound_list = info.get('inbound', [])
        if not inbound_list:
            return ""
       
        lines = ["    /* Inbound MQ Managers */"]
        inbound = colors["inbound"]
       
        for inbound_mgr in inbound_list:
            inbound_id = sanitize_id(inbound_mgr)
            inbound_dir = self._find_directorate(inbound_mgr)
            lines.extend([
                f"    {inbound_id} [shape=cylinder style=\"filled\" fillcolor=\"{inbound['fill']}\" color=\"{inbound['border']}\" penwidth=1.5",
                f"        label=<{inbound_mgr}<br/><font point-size='8'>{inbound_dir}</font>>]",
                f"    {inbound_id} -> {qm_id} [color=\"{inbound['arrow']}\" penwidth=2.0 label=\"sends to\"]"
            ])
       
        return "\n".join(lines) + "\n"
   
    def _outbound_nodes(self, info: Dict, qm_id: str, colors: Dict) -> str:
        """Generate outbound nodes."""
        from utils.common import sanitize_id
       
        outbound_list = info.get('outbound', [])
        if not outbound_list:
            return ""
       
        lines = ["    /* Outbound MQ Managers */"]
        outbound = colors["outbound"]
       
        for outbound_mgr in outbound_list:
            outbound_id = sanitize_id(outbound_mgr)
            outbound_dir = self._find_directorate(outbound_mgr)
            lines.extend([
                f"    {outbound_id} [shape=cylinder style=\"filled\" fillcolor=\"{outbound['fill']}\" color=\"{outbound['border']}\" penwidth=1.5",
                f"        label=<{outbound_mgr}<br/><font point-size='8'>{outbound_dir}</font>>]",
                f"    {qm_id} -> {outbound_id} [color=\"{outbound['arrow']}\" penwidth=2.0 label=\"sends to\"]"
            ])
       
        return "\n".join(lines) + "\n"
   
    def _external_nodes(self, info: Dict, qm_id: str, colors: Dict) -> str:
        """Generate external system nodes."""
        from utils.common import sanitize_id
       
        inbound_extra = info.get('inbound_extra', [])
        outbound_extra = info.get('outbound_extra', [])
       
        if not inbound_extra and not outbound_extra:
            return ""
       
        lines = []
        external = colors["external"]
       
        if inbound_extra:
            lines.append("    /* External Inbound */")
            for idx, ext in enumerate(inbound_extra):
                ext_id = f"ext_in_{idx}_{sanitize_id(ext[:20])}"
                lines.extend([
                    f'    {ext_id} [shape=box style="rounded,filled,dashed" fillcolor="{external["fill"]}" color="{external["border"]}" label="{ext}" fontsize=9]',
                    f'    {ext_id} -> {qm_id} [color="{external["arrow"]}" style=dashed label="external"]'
                ])
       
        if outbound_extra:
            lines.append("    /* External Outbound */")
            for idx, ext in enumerate(outbound_extra):
                ext_id = f"ext_out_{idx}_{sanitize_id(ext[:20])}"
                lines.extend([
                    f'    {ext_id} [shape=box style="rounded,filled,dashed" fillcolor="{external["fill"]}" color="{external["border"]}" label="{ext}" fontsize=9]',
                    f'    {qm_id} -> {ext_id} [color="{external["arrow"]}" style=dashed label="external"]'
                ])
       
        return "\n".join(lines) + "\n"
   
    def _legend(self, colors: Dict) -> str:
        """Generate legend."""
        return f"""    subgraph cluster_legend {{
        label="Legend" style="rounded,filled" fillcolor="#ffffff" color="#d0d8e0" fontsize=11 margin=15

        legend_item [shape=box style="rounded,filled" fillcolor="#f7f9fb"
            label=<
                <table border="0" cellborder="0" cellspacing="3" cellpadding="2">
                    <tr><td align="left"><font color="{colors['central']['border']}">🗄️</font> <b>This MQ Manager</b></td></tr>
                    <tr><td align="left"><font color="{colors['inbound']['arrow']}">🗄️</font> Inbound Sources</td></tr>
                    <tr><td align="left"><font color="{colors['outbound']['arrow']}">🗄️</font> Outbound Targets</td></tr>
                    <tr><td align="left"><font color="{colors['external']['arrow']}">⬜</font> External Systems</td></tr>
                </table>
            >
        ]
    }}"""
   
    def _find_directorate(self, mqmanager: str) -> str:
        """Find directorate for MQmanager."""
        for directorate, mqmanagers in self.data.items():
            if mqmanager in mqmanagers:
                return directorate
        return "Unknown"
   
    def generate_all(self, output_dir: Path) -> int:
        """Generate all individual diagrams."""
        output_dir.mkdir(parents=True, exist_ok=True)
        count = 0
       
        for directorate, mqmanagers in self.data.items():
            for mqmanager, info in mqmanagers.items():
                from utils.common import sanitize_id
                from generators.graphviz_topology import GraphVizTopologyGenerator
               
                dot_content = self.generate_diagram(mqmanager, directorate, info)
                safe_name = sanitize_id(mqmanager)
                dot_file = output_dir / f"{safe_name}.dot"
                pdf_file = output_dir / f"{safe_name}.pdf"
               
                dot_file.write_text(dot_content, encoding='utf-8')
                GraphVizTopologyGenerator.generate_pdf(dot_file, pdf_file)
                count += 1
       
        return count