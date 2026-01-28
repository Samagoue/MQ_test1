"""Full MQ topology diagram generator."""

import subprocess
import shutil
from typing import Dict, List
from pathlib import Path

class GraphVizTopologyGenerator:
    """Generate complete MQ topology diagrams."""
   
    def __init__(self, data: Dict, config):
        self.data = data
        self.config = config
        self.mqmanager_to_directorate = self._build_index()
   
    def _build_index(self) -> Dict[str, str]:
        """Build MQmanager to directorate lookup."""
        index = {}
        for directorate, mqmanagers in self.data.items():
            for mqmanager in mqmanagers.keys():
                index[mqmanager] = directorate
        return index
   
    def generate(self) -> str:
        """Generate complete DOT content."""
        from utils.common import sanitize_id
       
        sections = [
            self._generate_header(),
            self._generate_minimap(),
            self._generate_directorates(),
            self._generate_connections(),
            self._generate_legend(),
            "}"
        ]
        return "\n".join(sections)
   
    def _generate_header(self) -> str:
        """Generate DOT header."""
        cfg = self.config
        return f"""digraph MQ_Topology {{
    rankdir={cfg.GRAPHVIZ_RANKDIR}
    compound=true
    fontname="Helvetica"
    bgcolor="{cfg.GRAPHVIZ_BGCOLOR}"
    splines=curved
    nodesep={cfg.GRAPHVIZ_NODESEP}
    ranksep={cfg.GRAPHVIZ_RANKSEP}

    node [fontname="Helvetica" margin="0.45,0.30" penwidth=1.2]
    edge [fontname="Helvetica" fontsize=10 color="#5d6d7e" arrowsize=0.8]
"""
   
    def _generate_minimap(self) -> str:
        """Generate overview minimap (Top-Left)."""
        from utils.common import sanitize_id
       
        lines = [
            "    /* ==========================",
            "       MINI-MAP (Top-Left)",
            "    ========================== */",
            "    subgraph cluster_minimap {",
            '        label="Overview"',
            '        style="rounded,filled"',
            '        fillcolor="#ffffff"',
            '        color="#d0d8e0"',
            "        fontsize=12",
            "        margin=18",
            ""
        ]
       
        sorted_dirs = sorted(self.data.keys())
       
        # Create minimap nodes with proper formatting
        for idx, directorate in enumerate(sorted_dirs):
            colors = self.config.DIRECTORATE_COLORS[idx % len(self.config.DIRECTORATE_COLORS)]
            safe_name = sanitize_id(directorate).lower()
            lines.append(f'        mini_{safe_name}   [shape=box style="rounded,filled" fillcolor="{colors["org_bg"]}" label="{directorate}" fontsize=10]')
       
        # Create minimap connections
        if len(sorted_dirs) > 1:
            lines.append("")
            # First connection is solid blue
            if len(sorted_dirs) >= 2:
                from_node = sanitize_id(sorted_dirs[0]).lower()
                to_node = sanitize_id(sorted_dirs[1]).lower()
                lines.append(f'        mini_{from_node} -> mini_{to_node}       [color="#5dade2" arrowsize=0.5]')
           
            # Remaining connections are dashed red
            for i in range(len(sorted_dirs) - 1):
                if i > 0:  # Skip first connection, already added
                    from_node = sanitize_id(sorted_dirs[i]).lower()
                    to_node = sanitize_id(sorted_dirs[i + 1]).lower()
                    lines.append(f'        mini_{from_node} -> mini_{to_node} [color="#ec7063" arrowsize=0.5 style=dashed]')
       
        lines.extend(["    }", ""])
        return "\n".join(lines)
   
    def _generate_directorates(self) -> str:
        """Generate all directorate clusters."""
        from utils.common import sanitize_id
       
        sections = []
        for dir_idx, (directorate, mqmanagers) in enumerate(sorted(self.data.items())):
            colors = self.config.DIRECTORATE_COLORS[dir_idx % len(self.config.DIRECTORATE_COLORS)]
           
            lines = [
                f"    /* DIRECTORATE: {directorate} */",
                f'    subgraph cluster_{sanitize_id(directorate)} {{',
                f'        label="Directorate: {directorate}"',
                f'        style=filled fillcolor="{colors["org_bg"]}" color="{colors["org_border"]}"',
                f'        penwidth=2.5 fontsize=16 fontcolor="#2c3e50" margin=30', ""
            ]
           
            for mqmanager, info in sorted(mqmanagers.items()):
                lines.extend(self._generate_mqmanager_node(mqmanager, info, colors))
           
            lines.extend(["    }", ""])
            sections.append("\n".join(lines))
       
        return "\n".join(sections)
   
    def _generate_mqmanager_node(self, mqmanager: str, info: Dict, colors: Dict) -> List[str]:
        """Generate MQ Manager node."""
        from utils.common import sanitize_id
       
        qm_id = sanitize_id(mqmanager)
        return [
            f"        {qm_id} [",
            f'            shape=cylinder style="filled"',
            f'            fillcolor="{colors["qm_bg"]}" color="{colors["qm_border"]}"',
            f'            penwidth=1.8 fontcolor="{colors["qm_text"]}"',
            "            label=<",
            '                <table border="0" cellborder="0" cellspacing="0" cellpadding="3">',
            f'                    <tr><td align="center"><b>🗄️ {mqmanager}</b></td></tr>',
            f'                    <tr><td align="center"><font point-size="9">QLocal: {info.get("qlocal_count", 0)} | QRemote: {info.get("qremote_count", 0)} | QAlias: {info.get("qalias_count", 0)}</font></td></tr>',
            '                    <tr><td><br/></td></tr>',
            '                    <tr><td align="center"><b>Connections</b></td></tr>',
            f'                    <tr><td align="center"><font point-size="9">⬅ Inbound: {len(info.get("inbound", []))} | Outbound: {len(info.get("outbound", []))} ➡</font></td></tr>',
            "                </table>",
            "            >",
            "        ]", ""
        ]
   
    def _generate_connections(self) -> str:
        """Generate connection edges with proper formatting."""
        from utils.common import sanitize_id
       
        internal, cross = [], []
       
        for directorate, mqmanagers in self.data.items():
            for mqmanager, info in mqmanagers.items():
                for outbound in info.get('outbound', []):
                    target_dir = self.mqmanager_to_directorate.get(outbound, 'Unknown')
                    conn = {
                        'from': mqmanager, 'to': outbound,
                        'from_dir': directorate, 'to_dir': target_dir,
                        'label': f"{mqmanager}.{outbound}"
                    }
                    (internal if directorate == target_dir else cross).append(conn)
       
        sections = []
       
        # Internal connections
        if internal:
            lines = [
                "    /* ==========================",
                "       Internal Directorate Connections",
                "    ========================== */"
            ]
            for conn in internal:
                lines.append(
                    f'    {sanitize_id(conn["from"])} -> {sanitize_id(conn["to"])} '
                    f'[label="{conn["label"]}" color="#5dade2" penwidth=2.2 fontcolor="#2c3e50"]'
                )
            sections.append("\n".join(lines) + "\n")
       
        # Cross-directorate connections
        if cross:
            lines = [
                "    /* ==========================",
                "       Cross-Directorate Connections",
                "    ========================== */"
            ]
            for conn in cross:
                lines.append(
                    f'    {sanitize_id(conn["from"])} -> {sanitize_id(conn["to"])} '
                    f'[label="{conn["label"]}" color="#ec7063" penwidth=2.2 style=dashed fontcolor="#2c3e50"]'
                )
            sections.append("\n".join(lines) + "\n")
       
        return "\n".join(sections)
   
    def _generate_legend(self) -> str:
        """Generate legend matching the exact format."""
        sorted_dirs = sorted(self.data.keys())
        color_rows = []
        for idx, directorate in enumerate(sorted_dirs):
            colors = self.config.DIRECTORATE_COLORS[idx % len(self.config.DIRECTORATE_COLORS)]
            color_rows.append(
                f'                    <tr><td align="left">'
                f'<font color="{colors["org_bg"]}"><b>■</b></font> {directorate} Directorate</td></tr>'
            )
       
        return f"""    /* ==========================
       LEGEND (Modern Cloud Card)
    ========================== */
    subgraph cluster_legend {{
        label=<
            <b>Legend</b>
        >
        style="rounded,filled"
        fillcolor="#ffffff"
        color="#d0d8e0"
        penwidth=1.8
        fontsize=14
        margin=25

        legend_item [
            shape=box
            style="rounded,filled"
            fillcolor="#f7f9fb"
            color="#d6d6d6"
            penwidth=1
            label=<
                <table border="0" cellborder="0" cellspacing="4" cellpadding="2">

                    <tr><td align="left"><b>MQ Components</b></td></tr>
                    <tr><td align="left">🗄️ <b>Cylinder</b> — MQ Manager</td></tr>
                    <tr><td align="left">⦿ <b>Connections</b> — Inbound/Outbound count</td></tr>

                    <tr><td><br/></td></tr>

                    <tr><td align="left"><b>Queue Counts</b></td></tr>
                    <tr><td align="left"><b>QLocal</b> — Local queues</td></tr>
                    <tr><td align="left"><b>QRemote</b> — Remote queues</td></tr>
                    <tr><td align="left"><b>QAlias</b> — Alias queues</td></tr>

                    <tr><td><br/></td></tr>

                    <tr><td align="left"><b>Channel Types</b></td></tr>
                    <tr><td align="left"><font color="#5dade2"><b>────</b></font> Internal (Same Directorate)</td></tr>
                    <tr><td align="left"><font color="#ec7063"><b>- - - -</b></font> Cross-Directorate Channel</td></tr>

                    <tr><td><br/></td></tr>

                    <tr><td align="left"><b>Color Themes</b></td></tr>
{chr(10).join(color_rows)}

                </table>
            >
        ]
    }}"""
   
    def save_to_file(self, filepath: Path):
        """Save DOT content."""
        content = self.generate()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
        print(f"✓ DOT file saved: {filepath}")
   
    @staticmethod
    def generate_pdf(dot_file: Path, pdf_file: Path) -> bool:
        """Generate PDF from DOT file."""
        if not shutil.which('dot'):
            print("⚠ Graphviz 'dot' not found. Install from: https://graphviz.org/download/")
            return False
       
        try:
            subprocess.run(['dot', '-Tpdf', str(dot_file), '-o', str(pdf_file)], check=True, capture_output=True)
            print(f"✓ PDF generated: {pdf_file}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ PDF generation failed: {e}")
            return False
