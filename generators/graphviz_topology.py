
"""Full MQ topology diagram generator with directorate-level clustering."""

import subprocess
import shutil
from typing import Dict, List
from pathlib import Path
from utils.common import lighten_color, darken_color
from utils.logging_config import get_logger

logger = get_logger("generators.graphviz_topology")


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
 
    def _generate_directorates(self) -> str:
        """Generate all directorate clusters with gradient fills."""
        from utils.common import sanitize_id

        sections = []
        for dir_idx, (directorate, mqmanagers) in enumerate(sorted(self.data.items())):
            colors = self.config.DIRECTORATE_COLORS[dir_idx % len(self.config.DIRECTORATE_COLORS)]

            # Create gradient fill for directorate
            dir_bg = colors["org_bg"]
            dir_bg_light = lighten_color(dir_bg, 0.15)

            lines = [
                f"    /* DIRECTORATE: {directorate} */",
                f'    subgraph cluster_{sanitize_id(directorate)} {{',
                f'        label="Directorate: {directorate}"',
                f'        style=filled fillcolor="{dir_bg}:{dir_bg_light}" gradientangle=270',
                f'        color="{colors["org_border"]}"',
                f'        penwidth=2.5 fontsize=16 fontcolor="#2c3e50" margin=30', ""
            ]

            for mqmanager, info in sorted(mqmanagers.items()):
                lines.extend(self._generate_mqmanager_node(mqmanager, info, colors))

            lines.extend(["    }", ""])
            sections.append("\n".join(lines))

        return "\n".join(sections)
 
    def _generate_mqmanager_node(self, mqmanager: str, info: Dict, colors: Dict) -> List[str]:
        """Generate MQ Manager node with gradient fill."""
        from utils.common import sanitize_id

        qm_id = sanitize_id(mqmanager)

        # Create gradient fill for MQ manager node
        qm_bg = colors["qm_bg"]
        qm_bg_dark = darken_color(qm_bg, 0.08)

        return [
            f"        {qm_id} [",
            f'            shape=cylinder style="filled"',
            f'            fillcolor="{qm_bg}:{qm_bg_dark}" gradientangle=90',
            f'            color="{colors["qm_border"]}"',
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
        """Generate connection edges with bidirectional detection and proper formatting."""
        from utils.common import sanitize_id

        # Get connection colors and arrow styles from config
        conn_colors = self.config.CONNECTION_COLORS
        conn_arrows = self.config.CONNECTION_ARROWHEADS
        conn_tails = self.config.CONNECTION_ARROWTAILS

        # Collect all connections
        all_connections = []
        for directorate, mqmanagers in self.data.items():
            for mqmanager, info in mqmanagers.items():
                for outbound in info.get('outbound', []):
                    target_dir = self.mqmanager_to_directorate.get(outbound, 'Unknown')
                    conn = {
                        'from': mqmanager, 'to': outbound,
                        'from_dir': directorate, 'to_dir': target_dir,
                        'label': f"{mqmanager}.{outbound}"
                    }
                    all_connections.append(conn)

        # Build connection pairs to detect bidirectional
        connection_pairs = {}
        for conn in all_connections:
            pair_key = tuple(sorted([conn['from'], conn['to']]))
            if pair_key not in connection_pairs:
                connection_pairs[pair_key] = []
            connection_pairs[pair_key].append(conn)

        # Classify connections
        internal = []
        cross = []
        bidirectional = []
        processed_bidirectional = set()

        for conn in all_connections:
            pair_key = tuple(sorted([conn['from'], conn['to']]))

            # Check if this is a bidirectional connection
            reverse_exists = any(
                c['from'] == conn['to'] and c['to'] == conn['from']
                for c in connection_pairs.get(pair_key, [])
            )

            if reverse_exists and pair_key not in processed_bidirectional:
                # This is a bidirectional connection - add only once
                bidirectional.append(conn)
                processed_bidirectional.add(pair_key)
            elif not reverse_exists:
                # Single direction - classify normally
                if conn['from_dir'] == conn['to_dir']:
                    internal.append(conn)
                else:
                    cross.append(conn)

        sections = []

        # Internal connections - no explicit ports for shortest path
        # All edges: pointed arrow at destination, bullet at origin
        if internal:
            lines = [
                "    /* ==========================",
                "       Internal Directorate Connections",
                "    ========================== */"
            ]
            for conn in internal:
                lines.append(
                    f'    {sanitize_id(conn["from"])} -> {sanitize_id(conn["to"])} '
                    f'[label="{conn["label"]}" color="{conn_colors["same_dept"]}" penwidth=2.2 '
                    f'dir=both arrowhead={conn_arrows["same_dept"]} arrowtail={conn_tails["same_dept"]} fontcolor="#2c3e50" weight=3]'
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
                    f'[label="{conn["label"]}" color="{conn_colors["cross_dept"]}" penwidth=2.2 '
                    f'style=dashed dir=both arrowhead={conn_arrows["cross_dept"]} arrowtail={conn_tails["cross_dept"]} fontcolor="#2c3e50" weight=2]'
                )
            sections.append("\n".join(lines) + "\n")

        # Bidirectional connections - teal, bold, dir=both
        if bidirectional:
            lines = [
                "    /* ==========================",
                "       Bidirectional Connections",
                "    ========================== */"
            ]
            for conn in bidirectional:
                lines.append(
                    f'    {sanitize_id(conn["from"])} -> {sanitize_id(conn["to"])} '
                    f'[label="{conn["label"]}" color="{conn_colors["bidirectional"]}" penwidth=2.5 '
                    f'style=bold dir=both arrowhead={conn_arrows["bidirectional"]} arrowtail={conn_tails["bidirectional"]} fontcolor="#2c3e50" weight=1]'
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
                    <tr><td align="left"><font color="#1f78d1"><b>●────▶</b></font> Internal (Same Directorate, solid)</td></tr>
                    <tr><td align="left"><font color="#ff6b5a"><b>●- - -▶</b></font> Cross-Directorate (dashed)</td></tr>
                    <tr><td align="left"><font color="#00897b"><b>◀━━━▶</b></font> Bidirectional (bold)</td></tr>

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
        logger.info(f"✓ DOT file saved: {filepath}")
 
    @staticmethod
    def generate_pdf(dot_file: Path, pdf_file: Path) -> bool:
        """Generate PDF from DOT file."""
        if not shutil.which('dot'):
            logger.warning("⚠ Graphviz 'dot' not found. Install from: https://graphviz.org/download/")
            return False
     
        try:
            subprocess.run(['dot', '-Tpdf', str(dot_file), '-o', str(pdf_file)], check=True, capture_output=True)
            logger.info(f"✓ PDF generated: {pdf_file}")
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"✗ PDF generation failed: {e}")
            return False
