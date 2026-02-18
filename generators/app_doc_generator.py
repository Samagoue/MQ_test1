"""
Per-Application EA Documentation Generator.

Produces a concise, self-contained Confluence wiki-markup page for each
application in the MQ CMDB topology.  Each page uses a two-tab layout:

    Tab 1 — Documentation  (key metrics, MQ inventory, integration map)
    Tab 2 — Integration Diagram  (embedded SVG via {viewfile} macro)

Usage::

    from generators.app_doc_generator import ApplicationDocGenerator

    gen = ApplicationDocGenerator(enriched_data)
    gen.generate_all(Path("output/exports/app_docs"))
"""

import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Set

from utils.logging_config import get_logger

logger = get_logger("generators.app_doc_generator")

# Import markup helpers from the shared base class
import os, sys
_SHARED_SCRIPTS_DIR = os.environ.get("SHARED_SCRIPTS_DIR", r"C:/Users/BABED2P/Documents/WORKSPACE/Scripts")
if _SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SHARED_SCRIPTS_DIR)

try:
    from confluence_doc_generator import ConfluenceDocGenerator
except ImportError:
    from scripts.common.confluence_doc_generator import ConfluenceDocGenerator

# Reuse static helpers
_styled_panel = ConfluenceDocGenerator.styled_panel
_status_lozenge = ConfluenceDocGenerator.status_lozenge


def _sanitize_filename(name: str) -> str:
    """Sanitize app name to match the diagram generator's filename convention."""
    sanitized = re.sub(r'[^\w\s-]', '_', name)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = re.sub(r'_+', '_', sanitized)
    result = sanitized.strip('_').lower()
    return result if result else 'unnamed_app'


class ApplicationDocGenerator:
    """Generate per-application EA documentation pages in Confluence wiki markup."""

    def __init__(self, enriched_data: Dict):
        if not isinstance(enriched_data, dict):
            raise ValueError(f"enriched_data must be a dict, got {type(enriched_data).__name__}")
        self.data = enriched_data
        self.stats = self._calculate_statistics()
        self.dependencies = self._analyze_dependencies()

    # ------------------------------------------------------------------ #
    #  Data analysis (lightweight subset of EADocumentationGenerator)
    # ------------------------------------------------------------------ #

    def _calculate_statistics(self) -> Dict:
        """Build per-MQ-manager stats and per-app capability map."""
        mqmanagers: Dict[str, Dict] = {}
        apps: Dict[str, Dict] = {}

        for org_name, org_data in self.data.items():
            if not isinstance(org_data, dict) or '_departments' not in org_data:
                continue
            org_type = org_data.get('_org_type', 'Internal')

            for dept_name, dept_data in org_data['_departments'].items():
                for biz_ownr, applications in dept_data.items():
                    for app_name, mqmgr_dict in applications.items():
                        for mqmgr_name, mqmgr_data in mqmgr_dict.items():
                            mqmanagers[mqmgr_name] = {
                                'org': org_name, 'org_type': org_type,
                                'dept': dept_name, 'biz_ownr': biz_ownr,
                                'app': app_name,
                                'is_gateway': mqmgr_data.get('IsGateway', False),
                                'mq_host': mqmgr_data.get('mq_host', ''),
                                'qlocal': mqmgr_data.get('qlocal_count', 0),
                                'qremote': mqmgr_data.get('qremote_count', 0),
                                'qalias': mqmgr_data.get('qalias_count', 0),
                                'inbound': mqmgr_data.get('inbound', []),
                                'outbound': mqmgr_data.get('outbound', []),
                                'inbound_extra': mqmgr_data.get('inbound_extra', []),
                                'outbound_extra': mqmgr_data.get('outbound_extra', []),
                            }

                            if app_name and not app_name.startswith('Gateway (') and app_name != 'No Application':
                                if app_name not in apps:
                                    apps[app_name] = {
                                        'org': org_name, 'org_type': org_type,
                                        'dept': dept_name, 'biz_ownr': biz_ownr,
                                        'mqmanagers': [],
                                        'total_queues': 0, 'connections': 0,
                                    }
                                apps[app_name]['mqmanagers'].append(mqmgr_name)
                                apps[app_name]['total_queues'] += (
                                    mqmgr_data.get('qlocal_count', 0)
                                    + mqmgr_data.get('qremote_count', 0)
                                    + mqmgr_data.get('qalias_count', 0)
                                )
                                apps[app_name]['connections'] += (
                                    len(mqmgr_data.get('outbound', []))
                                    + len(mqmgr_data.get('inbound', []))
                                )

        return {'mqmanagers': mqmanagers, 'apps': apps}

    def _analyze_dependencies(self) -> Dict[str, Set[str]]:
        """Build app-to-app dependency map (outbound direction)."""
        deps: Dict[str, Set[str]] = defaultdict(set)
        for mqmgr_name, info in self.stats['mqmanagers'].items():
            src_app = info['app']
            if not src_app or src_app.startswith('Gateway ('):
                continue
            for target in info.get('outbound', []):
                target_info = self.stats['mqmanagers'].get(target, {})
                tgt_app = target_info.get('app', '')
                if tgt_app and tgt_app != src_app and not tgt_app.startswith('Gateway ('):
                    deps[src_app].add(tgt_app)
        return deps

    # ------------------------------------------------------------------ #
    #  Per-app page generation
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize(name: str) -> str:
        """Normalize an app name for fuzzy matching (lowercase, collapse separators)."""
        return re.sub(r'[\s_\-]+', '', name).lower()

    def _resolve_app_name(self, app_name: str) -> Optional[str]:
        """Resolve an app name from config to the exact name in the data.

        Tries (in order): exact match, case-insensitive, normalized
        (ignoring spaces/underscores/hyphens).
        Returns the canonical app name or None if not found.
        """
        if app_name in self.stats['apps']:
            return app_name
        # Case-insensitive fallback
        lower = app_name.lower()
        for known in self.stats['apps']:
            if known.lower() == lower:
                return known
        # Normalized fallback (collapse spaces, underscores, hyphens)
        norm = self._normalize(app_name)
        for known in self.stats['apps']:
            if self._normalize(known) == norm:
                logger.info(f"  Fuzzy-matched config name '{app_name}' → data name '{known}'")
                return known
        return None

    def get_known_apps(self) -> List[str]:
        """Return the list of application names known to this generator."""
        return sorted(self.stats['apps'].keys())

    def generate_app_page(self, app_name: str) -> Optional[str]:
        """Return Confluence wiki markup for one application's documentation page."""
        resolved = self._resolve_app_name(app_name)
        if not resolved:
            return None
        app_name = resolved

        app_info = self.stats['apps'][app_name]
        mqmanagers = self.stats['mqmanagers']
        svg_filename = f"{_sanitize_filename(app_name)}.svg"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines: List[str] = []

        # ---- Documentation section ----

        # Header panel
        lines.extend(_styled_panel(app_name, [
            "||Property||Value||",
            f"|*Organization*|{app_info['org']}|",
            f"|*Department*|{app_info['dept']}|",
            f"|*Business Owner*|{app_info['biz_ownr']}|",
            f"|*Type*|{_status_lozenge(app_info['org_type'], 'Green' if app_info['org_type'] == 'Internal' else 'Blue')}|",
        ], bg_color="#f7f9fb", title_bg="#1565c0", title_color="#fff", border_color="#90caf9"))
        lines.append("")

        # Key metrics cards
        total_inbound = 0
        total_outbound = 0
        total_qlocal = 0
        total_qremote = 0
        total_qalias = 0
        for mgr_name in app_info['mqmanagers']:
            mgr = mqmanagers.get(mgr_name, {})
            total_qlocal += mgr.get('qlocal', 0)
            total_qremote += mgr.get('qremote', 0)
            total_qalias += mgr.get('qalias', 0)
            total_inbound += len(mgr.get('inbound', [])) + len(mgr.get('inbound_extra', []))
            total_outbound += len(mgr.get('outbound', [])) + len(mgr.get('outbound_extra', []))

        lines.extend([
            "h3. Key Metrics",
            "",
            "{section}",
            "{column:width=33%}",
            *_styled_panel("MQ Managers", [
                f"h2. {len(app_info['mqmanagers'])}",
                "Queue Managers",
            ], bg_color="#e3f2fd", title_bg="#1565c0", title_color="#fff", border_color="#90caf9"),
            "{column}",
            "{column:width=33%}",
            *_styled_panel("Total Queues", [
                f"h2. {app_info['total_queues']:,}",
                f"Local: {total_qlocal:,} | Remote: {total_qremote:,} | Alias: {total_qalias:,}",
            ], bg_color="#e8f5e9", title_bg="#2e7d32", title_color="#fff", border_color="#a5d6a7"),
            "{column}",
            "{column:width=33%}",
            *_styled_panel("Connections", [
                f"h2. {total_inbound + total_outbound}",
                f"Inbound: {total_inbound} | Outbound: {total_outbound}",
            ], bg_color="#fff3e0", title_bg="#e65100", title_color="#fff", border_color="#ffcc80"),
            "{column}",
            "{section}",
            "",
        ])

        # MQ Manager inventory table
        lines.extend([
            "h3. MQ Manager Inventory",
            "",
            "||MQ Manager||Host||Local||Remote||Alias||Total||Gateway||",
        ])
        for mgr_name in sorted(app_info['mqmanagers']):
            mgr = mqmanagers.get(mgr_name, {})
            host = mgr.get('mq_host', '') or ' '
            ql = mgr.get('qlocal', 0)
            qr = mgr.get('qremote', 0)
            qa = mgr.get('qalias', 0)
            gw = _status_lozenge("Yes", "Blue") if mgr.get('is_gateway') else " "
            lines.append(f"|{mgr_name}|{host}|{ql:,}|{qr:,}|{qa:,}|{ql+qr+qa:,}|{gw}|")
        lines.append("")

        # Integration map — inbound
        _unmapped = {'No Application', 'Unknown'}
        _RED = "{color:#cc0000}"
        _ENDC = "{color}"
        inbound_rows = []
        has_unmapped_inbound = False
        for mgr_name in app_info['mqmanagers']:
            mgr = mqmanagers.get(mgr_name, {})
            for source in mgr.get('inbound', []):
                src_info = mqmanagers.get(source, {})
                src_app = src_info.get('app', 'Unknown')
                if src_app != app_name:
                    if src_app in _unmapped:
                        has_unmapped_inbound = True
                        loz = _status_lozenge('NEEDS MAPPING', 'Red')
                        inbound_rows.append(
                            f"|{_RED}{source}{_ENDC}"
                            f"|{_RED}*{src_app}*{_ENDC} {loz}"
                            f"|{mgr_name}|"
                        )
                    else:
                        inbound_rows.append(f"|{source}|{src_app}|{mgr_name}|")
            for source in mgr.get('inbound_extra', []):
                inbound_rows.append(f"|{source}|_(External)_|{mgr_name}|")

        # Integration map — outbound
        outbound_rows = []
        has_unmapped_outbound = False
        for mgr_name in app_info['mqmanagers']:
            mgr = mqmanagers.get(mgr_name, {})
            for target in mgr.get('outbound', []):
                tgt_info = mqmanagers.get(target, {})
                tgt_app = tgt_info.get('app', 'Unknown')
                if tgt_app != app_name:
                    if tgt_app in _unmapped:
                        has_unmapped_outbound = True
                        loz = _status_lozenge('NEEDS MAPPING', 'Red')
                        outbound_rows.append(
                            f"|{mgr_name}"
                            f"|{_RED}{target}{_ENDC}"
                            f"|{_RED}*{tgt_app}*{_ENDC} {loz}|"
                        )
                    else:
                        outbound_rows.append(f"|{mgr_name}|{target}|{tgt_app}|")
            for target in mgr.get('outbound_extra', []):
                outbound_rows.append(f"|{mgr_name}|{target}|_(External)_|")

        if inbound_rows or outbound_rows:
            lines.append("h3. Integration Map")
            lines.append("")

            if has_unmapped_inbound or has_unmapped_outbound:
                lines.extend([
                    "{info:title=Action Required}",
                    "Some MQ Managers highlighted below are not yet mapped to an application.",
                    "Please update the *App to QMgr Mapping* page in Confluence to add the missing entries.",
                    "{info}",
                    "",
                ])

            if inbound_rows:
                lines.extend([
                    "h4. Inbound Connections",
                    "",
                    "||Source MQ Manager||Source Application||Target MQ Manager||",
                    *inbound_rows,
                    "",
                ])
            if outbound_rows:
                lines.extend([
                    "h4. Outbound Connections",
                    "",
                    "||Source MQ Manager||Target MQ Manager||Target Application||",
                    *outbound_rows,
                    "",
                ])

        # Application dependencies — RACI-style matrix
        outgoing_deps = self.dependencies.get(app_name, set())
        incoming_deps = {src for src, targets in self.dependencies.items() if app_name in targets}

        if outgoing_deps or incoming_deps:
            all_deps = sorted(outgoing_deps | incoming_deps)
            lines.extend(["h3. Application Dependencies", ""])
            lines.append("||Application||Data Flow||")
            for dep in all_deps:
                badges = []
                if dep in outgoing_deps:
                    badges.append("{status:colour=Yellow|title=SENDS TO}")
                if dep in incoming_deps:
                    badges.append("{status:colour=Grey|title=RECEIVES FROM}")
                lines.append(f"|{dep}|{' '.join(badges)}|")
            lines.append("")

        # Risk indicators
        risk_lines = []
        for mgr_name in app_info['mqmanagers']:
            mgr = mqmanagers.get(mgr_name, {})
            out_count = len(mgr.get('outbound', [])) + len(mgr.get('outbound_extra', []))
            in_count = len(mgr.get('inbound', [])) + len(mgr.get('inbound_extra', []))
            if out_count > 8:
                risk_lines.append(f"* *High fan-out:* {mgr_name} has {out_count} outbound connections")
            if in_count > 8:
                risk_lines.append(f"* *High fan-in:* {mgr_name} has {in_count} inbound connections")

        if risk_lines:
            lines.extend([
                "h3. Risk Indicators",
                "",
                "{warning:title=Attention}",
                *risk_lines,
                "{warning}",
                "",
            ])

        # ---- Integration Diagram section (collapsible) ----
        lines.extend([
            "----",
            "",
            "{expand:title=Integration Diagram}",
            "",
            f"{{viewfile:name={svg_filename}|height=800}}",
            "",
            "{expand}",
            "",
            "----",
            f"{{color:#999999}}_Auto-generated by MQ CMDB Pipeline — {timestamp}_{{color}}",
        ])

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Bulk generation
    # ------------------------------------------------------------------ #

    def generate_all(self, output_dir: Path) -> Dict:
        """Generate documentation files for all applications.

        Args:
            output_dir: Directory to write per-app .txt files

        Returns:
            Summary dict with 'generated' count and 'apps' list
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        summary = {'generated': 0, 'apps': []}

        for app_name in sorted(self.stats['apps'].keys()):
            markup = self.generate_app_page(app_name)
            if markup:
                filename = f"{_sanitize_filename(app_name)}.txt"
                filepath = output_dir / filename
                filepath.write_text(markup, encoding='utf-8')
                summary['generated'] += 1
                summary['apps'].append(app_name)

        logger.info(f"Generated {summary['generated']} per-application documentation files in {output_dir}")
        return summary
