"""
Consolidated Report Generator

Combines the Change Detection and Gateway Analytics reports into a single
HTML document with tab navigation, so both views are accessible from one file.
Uses the shared report_styles.py for consistent look and feel.
"""

from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from utils.logging_config import get_logger

logger = get_logger("utils.report_consolidator")


def generate_consolidated_report(
    changes: Optional[Dict],
    gateway_analytics: Optional[Dict],
    output_file: Path,
    current_timestamp: str,
    baseline_timestamp: str = None,
    enriched_data: Optional[Dict] = None,
) -> Path:
    """
    Generate a single HTML report combining change detection and gateway analytics.

    Each report appears as a separate tab with navigation at the top.
    Gracefully handles missing data (no baseline, no gateways).

    Args:
        changes: Change detection dict from ChangeDetector.compare(), or None
        gateway_analytics: Gateway analytics dict from GatewayAnalyzer.analyze(), or None
        output_file: Path to write the consolidated HTML file
        current_timestamp: Current pipeline run timestamp
        baseline_timestamp: Baseline timestamp string, or None if no baseline

    Returns:
        Path to the generated file
    """
    from utils.report_styles import get_report_css, get_report_js

    report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    routers = _extract_routers(enriched_data)

    # Build CSS: shared base (blue accent default) + tab navigation overrides
    base_css = get_report_css('#3498db')
    tab_css = _get_tab_css()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MQ CMDB Consolidated Report</title>
    <style>{base_css}
    {tab_css}
    </style>
</head>
<body>
    <div class="tab-bar">
        <span class="tab-bar-title">MQ CMDB Report</span>
        <button class="tab-btn active" id="btn-changes" onclick="showTab('changes')">Change Detection</button>
        <button class="tab-btn" id="btn-gateways" onclick="showTab('gateways')">Gateway Analytics</button>
        <button class="tab-btn" id="btn-routers" onclick="showTab('routers')">Routers</button>
    </div>

    <div id="tab-changes" class="tab-pane active">
"""

    # -- Change Detection tab --
    html += _build_changes_tab(changes, current_timestamp, baseline_timestamp, report_time)

    html += """
    </div>

    <div id="tab-gateways" class="tab-pane">
"""

    # -- Gateway Analytics tab --
    html += _build_gateways_tab(gateway_analytics, report_time)

    html += """
    </div>

    <div id="tab-routers" class="tab-pane">
"""

    # -- Routers tab --
    html += _build_routers_tab(routers, report_time)

    html += """
    </div>

"""

    html += f"""
    <script>{get_report_js()}

    /* Tab switching */
    function showTab(tab) {{
        document.querySelectorAll('.tab-pane').forEach(function(el) {{ el.classList.remove('active'); }});
        document.querySelectorAll('.tab-btn').forEach(function(el) {{ el.classList.remove('active'); }});
        document.getElementById('tab-' + tab).classList.add('active');
        document.getElementById('btn-' + tab).classList.add('active');

        /* Swap accent colour so section borders and cards match the active tab */
        document.documentElement.style.setProperty(
            '--accent',
            tab === 'gateways' ? '#9b59b6' : tab === 'routers' ? '#e67e22' : '#3498db'
        );
    }}
    </script>
</body>
</html>
"""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"Consolidated report generated: {output_file}")
    return output_file


# ---------------------------------------------------------------------------
# Tab navigation CSS (layered on top of the shared report_styles)
# ---------------------------------------------------------------------------

def _get_tab_css() -> str:
    """Additional CSS for the tab navigation bar and pane switching."""
    return """
        /* Override hero - we use the tab bar instead */
        .hero { margin-top: 0; }

        /* Tab navigation bar */
        .tab-bar {
            position: sticky; top: 0; z-index: 200;
            background: #1e293b;
            padding: 0 24px;
            display: flex; align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,.25);
        }
        .tab-bar-title {
            color: #fff; font-size: 15px; font-weight: 700;
            margin-right: 28px; padding: 13px 0; white-space: nowrap;
            letter-spacing: -.2px;
        }
        .tab-btn {
            background: none; border: none;
            color: #94a3b8; font-size: 13px; font-weight: 600;
            padding: 13px 18px; cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: color .2s, border-color .2s;
            font-family: inherit; letter-spacing: .2px;
        }
        .tab-btn:hover { color: #fff; }
        .tab-btn.active {
            color: #fff;
            border-bottom-color: var(--accent);
        }

        /* Tab panes */
        .tab-pane { display: none; }
        .tab-pane.active { display: block; }

        /* No-data placeholder */
        .no-data {
            text-align: center; padding: 80px 20px; color: var(--text-muted);
        }
        .no-data h2 { color: var(--text-muted); border: none; }
"""


# ---------------------------------------------------------------------------
# Change Detection tab
# ---------------------------------------------------------------------------

def _build_changes_tab(changes, current_timestamp, baseline_timestamp, report_time):
    """Build the Change Detection tab content."""
    if changes is None:
        return """
        <div class="no-data">
            <h2>No Change Detection Data</h2>
            <p>No baseline was available for comparison during this pipeline run.</p>
            <p>A baseline has been created. Changes will be detected on the next run.</p>
        </div>
"""

    summary = changes.get('summary', {})

    html = f"""
    <div class="hero">
        <h1>MQ CMDB Change Detection Report</h1>
        <p>Baseline vs. current snapshot comparison</p>
        <div class="meta">
            <span>Baseline: {baseline_timestamp or 'N/A'}</span>
            <span>Current: {current_timestamp}</span>
            <span>Generated: {report_time}</span>
        </div>
    </div>

    <div class="container">
        <div class="summary">
            <div class="summary-card accent">
                <h3>Total Changes</h3>
                <div class="count">{summary.get('total_changes', 0)}</div>
            </div>
            <div class="summary-card added">
                <h3>Managers Added</h3>
                <div class="count">{summary.get('mqmanagers_added', 0)}</div>
            </div>
            <div class="summary-card removed">
                <h3>Managers Removed</h3>
                <div class="count">{summary.get('mqmanagers_removed', 0)}</div>
            </div>
            <div class="summary-card modified">
                <h3>Managers Modified</h3>
                <div class="count">{summary.get('mqmanagers_modified', 0)}</div>
            </div>
            <div class="summary-card added">
                <h3>Connections Added</h3>
                <div class="count">{summary.get('connections_added', 0)}</div>
            </div>
            <div class="summary-card removed">
                <h3>Connections Removed</h3>
                <div class="count">{summary.get('connections_removed', 0)}</div>
            </div>
        </div>
"""

    mqmgrs = changes.get('mqmanagers', {})
    conns = changes.get('connections', {})
    gateways = changes.get('gateways', {})

    # MQ Managers Added
    if mqmgrs.get('added'):
        html += _section_open("MQ Managers Added")
        html += _table_open(["MQ Manager", "Organization", "Department", "Application", "Type"])
        rows = []
        for mgr in mqmgrs['added']:
            gateway_badge = '<span class="badge badge-gateway">Gateway</span>' if mgr.get('is_gateway') else ''
            rows.append(f"""
                    <tr>
                        <td><strong>{mgr.get('name', '')}</strong></td>
                        <td>{mgr.get('organization', '')}</td>
                        <td>{mgr.get('department', '')}</td>
                        <td>{mgr.get('application', '')}</td>
                        <td>{gateway_badge}</td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _section_close()

    # MQ Managers Removed
    if mqmgrs.get('removed'):
        html += _section_open("MQ Managers Removed")
        html += _table_open(["MQ Manager", "Organization", "Department", "Application"])
        rows = []
        for mgr in mqmgrs['removed']:
            rows.append(f"""
                    <tr>
                        <td><strong>{mgr.get('name', '')}</strong></td>
                        <td>{mgr.get('organization', '')}</td>
                        <td>{mgr.get('department', '')}</td>
                        <td>{mgr.get('application', '')}</td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _section_close()

    # MQ Managers Modified
    if mqmgrs.get('modified'):
        html += _section_open("MQ Managers Modified")
        html += _table_open(["MQ Manager", "Changes"])
        rows = []
        for mgr in mqmgrs['modified']:
            changes_text = '<br>'.join(
                f"{field}: {c.get('old', '')} &rarr; {c.get('new', '')}"
                for field, c in mgr.get('changes', {}).items()
            )
            rows.append(f"""
                    <tr>
                        <td><strong>{mgr.get('name', '')}</strong></td>
                        <td class="change-detail">{changes_text}</td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _section_close()

    # Connections Added
    if conns.get('added'):
        html += _section_open("Connections Added")
        html += _table_open(["Source", "Target", "Source Org", "Target Org"])
        rows = []
        for conn in conns['added']:
            rows.append(f"""
                    <tr>
                        <td>{conn.get('source', '')}</td>
                        <td>{conn.get('target', '')}</td>
                        <td>{conn.get('source_org', '')}</td>
                        <td>{conn.get('target_org', '')}</td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _section_close()

    # Connections Removed
    if conns.get('removed'):
        html += _section_open("Connections Removed")
        html += _table_open(["Source", "Target", "Source Org", "Target Org"])
        rows = []
        for conn in conns['removed']:
            rows.append(f"""
                    <tr>
                        <td>{conn.get('source', '')}</td>
                        <td>{conn.get('target', '')}</td>
                        <td>{conn.get('source_org', '')}</td>
                        <td>{conn.get('target_org', '')}</td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _section_close()

    # Gateway Changes
    if gateways.get('added') or gateways.get('removed') or gateways.get('modified'):
        html += _section_open("Gateway Changes")

        if gateways.get('added'):
            html += _details_open("Added Gateways")
            html += _table_open(["Gateway Name", "Scope", "Organization", "Department"])
            rows = []
            for gw in gateways['added']:
                rows.append(f"""
                    <tr>
                        <td><strong>{gw.get('name', '')}</strong></td>
                        <td><span class="badge badge-gateway">{gw.get('scope', '')}</span></td>
                        <td>{gw.get('organization', '')}</td>
                        <td>{gw.get('department', '')}</td>
                    </tr>""")
            html += "".join(rows)
            html += _table_close() + _details_close()

        if gateways.get('removed'):
            html += _details_open("Removed Gateways")
            html += _table_open(["Gateway Name", "Scope", "Organization"])
            rows = []
            for gw in gateways['removed']:
                rows.append(f"""
                    <tr>
                        <td><strong>{gw.get('name', '')}</strong></td>
                        <td><span class="badge badge-gateway">{gw.get('scope', '')}</span></td>
                        <td>{gw.get('organization', '')}</td>
                    </tr>""")
            html += "".join(rows)
            html += _table_close() + _details_close()

        if gateways.get('modified'):
            html += _details_open("Modified Gateway Scopes")
            html += _table_open(["Gateway Name", "Old Scope", "New Scope"])
            rows = []
            for gw in gateways['modified']:
                rows.append(f"""
                    <tr>
                        <td><strong>{gw.get('name', '')}</strong></td>
                        <td>{gw.get('old_scope', '')}</td>
                        <td>{gw.get('new_scope', '')}</td>
                    </tr>""")
            html += "".join(rows)
            html += _table_close() + _details_close()

        html += _section_close()

    # Queue Count Changes
    if changes.get('queue_counts'):
        html += _section_open("Significant Queue Count Changes (&gt;20%)")
        html += _table_open(["MQ Manager", "Queue Type", "Old Count", "New Count", "Change %"])
        rows = []
        for qc in changes['queue_counts']:
            direction = "added" if qc.get('new_count', 0) > qc.get('old_count', 0) else "removed"
            rows.append(f"""
                    <tr>
                        <td>{qc.get('mqmanager', '')}</td>
                        <td>{qc.get('queue_type', '')}</td>
                        <td>{qc.get('old_count', '')}</td>
                        <td>{qc.get('new_count', '')}</td>
                        <td><span class="badge badge-{direction}">{qc.get('change_percent', '')}%</span></td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _section_close()

    # No changes message
    if summary.get('total_changes', 0) == 0:
        html += """
        <div class="no-changes">
            <h2>No Changes Detected</h2>
            <p>The current MQ CMDB data is identical to the baseline.</p>
        </div>
"""

    html += """
    </div>
"""
    return html


# ---------------------------------------------------------------------------
# Gateway Analytics tab
# ---------------------------------------------------------------------------

def _build_gateways_tab(gateway_analytics, report_time):
    """Build the Gateway Analytics tab content."""
    if gateway_analytics is None:
        return """
        <div class="no-data">
            <h2>No Gateway Analytics Data</h2>
            <p>No gateways were found in the current dataset, or gateway analysis was not performed.</p>
        </div>
"""

    summary = gateway_analytics.get('summary', {})

    # Max load score for CSS bar charts
    load_dist = gateway_analytics.get('load_distribution', {})
    all_loads = (load_dist.get('internal_gateways', []) +
                 load_dist.get('external_gateways', []))
    max_load = max((ld['load_score'] for ld in all_loads), default=1) or 1

    html = f"""
    <div class="hero" style="background: linear-gradient(135deg, #1e293b 0%, #334155 50%, #9b59b6 100%);">
        <h1>Gateway Analytics Report</h1>
        <p>Traffic patterns, dependencies, and redundancy analysis</p>
        <div class="meta">
            <span>Generated: {report_time}</span>
            <span>Gateways analyzed: {summary.get('total_gateways', 0)}</span>
        </div>
    </div>

    <div class="container">
        <div class="summary">
            <div class="summary-card accent">
                <h3>Total Gateways</h3>
                <div class="count">{summary.get('total_gateways', 0)}</div>
            </div>
            <div class="summary-card internal">
                <h3>Internal</h3>
                <div class="count">{summary.get('internal_gateways', 0)}</div>
            </div>
            <div class="summary-card external">
                <h3>External</h3>
                <div class="count">{summary.get('external_gateways', 0)}</div>
            </div>
            <div class="summary-card">
                <h3>Total Connections</h3>
                <div class="count">{summary.get('total_gateway_connections', 0)}</div>
            </div>
        </div>

        <div class="section">
            <h2>Gateway Traffic Overview</h2>
            <table>
                <thead>
                    <tr>
                        <th>Gateway</th>
                        <th>Scope</th>
                        <th>Organization</th>
                        <th>Inbound</th>
                        <th>Outbound</th>
                        <th>Total</th>
                        <th>Connected Orgs</th>
                        <th>Connected Depts</th>
                    </tr>
                </thead>
                <tbody>
"""

    rows = []
    for gw_name, traffic in sorted(gateway_analytics.get('gateway_traffic', {}).items(),
                                    key=lambda x: x[1].get('total_connections', 0), reverse=True):
        scope = traffic.get('scope', '')
        scope_class = scope.lower() if scope else 'internal'
        scope_badge = f'<span class="badge badge-{scope_class}">{scope}</span>'
        rows.append(f"""
                    <tr>
                        <td><strong>{gw_name}</strong></td>
                        <td>{scope_badge}</td>
                        <td>{traffic.get('organization', '')}</td>
                        <td>{traffic.get('inbound_connections', 0)}</td>
                        <td>{traffic.get('outbound_connections', 0)}</td>
                        <td><strong>{traffic.get('total_connections', 0)}</strong></td>
                        <td>{traffic.get('connected_organizations', 0)}</td>
                        <td>{traffic.get('connected_departments', 0)}</td>
                    </tr>""")
    html += "".join(rows)

    html += """
                </tbody>
            </table>
        </div>
"""

    # Redundancy Analysis
    redundancy = gateway_analytics.get('redundancy_analysis', {})
    if redundancy.get('spof_count', 0) > 0:
        html += f"""
        <div class="alert alert-danger">
            <h3>Single Points of Failure Detected</h3>
            <p>Found <strong>{redundancy.get('spof_count', 0)}</strong> critical routes with no gateway redundancy.</p>
        </div>
"""
        html += _section_open("Single Points of Failure")
        html += _table_open(["Route", "Type", "Gateway", "Connections"])
        rows = []
        for spof in redundancy.get('single_points_of_failure', []):
            rows.append(f"""
                    <tr>
                        <td>{spof.get('route', '')}</td>
                        <td>{spof.get('type', '')}</td>
                        <td><strong>{spof.get('gateway', '')}</strong></td>
                        <td>{spof.get('connection_count', 0)}</td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _section_close()
    else:
        html += """
        <div class="alert alert-success">
            <h3>Gateway Redundancy OK</h3>
            <p>All critical routes have redundant gateways configured.</p>
        </div>
"""

    # Load Distribution with CSS bar charts
    html += _section_open("Load Distribution")

    if load_dist.get('internal_gateways'):
        html += _details_open("Internal Gateways")
        html += _table_open(["Gateway", "Connections", "Queues", "Load Score"])
        rows = []
        for ld in load_dist['internal_gateways']:
            bar_pct = int(ld.get('load_score', 0) / max_load * 100)
            rows.append(f"""
                    <tr>
                        <td>{ld.get('gateway', '')}</td>
                        <td>{ld.get('connections', 0)}</td>
                        <td>{ld.get('queues', 0)}</td>
                        <td>
                            <div class="bar-wrap">
                                <div class="bar" style="width:{bar_pct}%"></div>
                                <span class="bar-label">{ld.get('load_score', 0)}</span>
                            </div>
                        </td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _details_close()

    if load_dist.get('external_gateways'):
        html += _details_open("External Gateways")
        html += _table_open(["Gateway", "Connections", "Queues", "Load Score"])
        rows = []
        for ld in load_dist['external_gateways']:
            bar_pct = int(ld.get('load_score', 0) / max_load * 100)
            rows.append(f"""
                    <tr>
                        <td>{ld.get('gateway', '')}</td>
                        <td>{ld.get('connections', 0)}</td>
                        <td>{ld.get('queues', 0)}</td>
                        <td>
                            <div class="bar-wrap">
                                <div class="bar" style="width:{bar_pct}%"></div>
                                <span class="bar-label">{ld.get('load_score', 0)}</span>
                            </div>
                        </td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _details_close()

    html += _section_close()

    # Organization Connectivity Matrix
    html += _section_open("Organization Connectivity Matrix")
    html += _table_open(["Organization Route", "Gateways", "Connections", "Redundancy"])
    rows = []
    for route, data in sorted(gateway_analytics.get('org_connectivity', {}).items(),
                               key=lambda x: x[1].get('connection_count', 0), reverse=True):
        gws = data.get('gateways', [])
        redundancy_badge = ('<span class="badge badge-ok">Yes</span>'
                            if len(gws) > 1
                            else '<span class="badge badge-warning">No</span>')
        rows.append(f"""
                    <tr>
                        <td>{route}</td>
                        <td>{', '.join(gws)}</td>
                        <td>{data.get('connection_count', 0)}</td>
                        <td>{redundancy_badge}</td>
                    </tr>""")
    html += "".join(rows)
    html += _table_close() + _section_close()

    # Gateway Dependencies (collapsible per gateway)
    if gateway_analytics.get('gateway_dependencies'):
        html += _section_open("Gateway Dependencies")
        for gw_name, deps in sorted(gateway_analytics['gateway_dependencies'].items()):
            apps_list = ', '.join(deps['dependent_applications']) if deps['dependent_applications'] else 'None'
            html += f"""
            <details>
                <summary>{gw_name} &mdash; {deps['application_count']} apps, {deps['dependent_mqmanagers']} MQ managers</summary>
                <div class="detail-body">
                    <p><strong>Dependent Applications:</strong> {apps_list}</p>
                </div>
            </details>
"""
        html += _section_close()

    html += """
    </div>
"""
    return html


# ---------------------------------------------------------------------------
# Routers tab
# ---------------------------------------------------------------------------

def _extract_routers(enriched_data: Optional[Dict]) -> list:
    """Extract router entries from enriched_data."""
    routers = []
    if not enriched_data:
        return routers
    for org_name, org_data in enriched_data.items():
        for dept_name, biz_owners in org_data.get('_departments', {}).items():
            for biz_ownr, apps in biz_owners.items():
                for mqmgr_name, mq_data in apps.get('Router', {}).items():
                    if mq_data.get('IsRouter', False):
                        routers.append({
                            'name': mqmgr_name,
                            'description': mq_data.get('RouterDescription', ''),
                            'organization': org_name,
                            'department': dept_name,
                            'inbound': len(mq_data.get('inbound', [])) + len(mq_data.get('inbound_extra', [])),
                            'outbound': len(mq_data.get('outbound', [])) + len(mq_data.get('outbound_extra', [])),
                        })
    return sorted(routers, key=lambda r: r['name'])


def _build_routers_tab(routers: list, report_time: str) -> str:
    """Build the Routers tab content."""
    html = f"""
    <div class="hero" style="background: linear-gradient(135deg, #1e293b 0%, #334155 50%, #e67e22 100%);">
        <h1>Routers</h1>
        <p>MQ Manager nodes acting as message routers</p>
        <div class="meta">
            <span>Generated: {report_time}</span>
            <span>Routers found: {len(routers)}</span>
        </div>
    </div>

    <div class="container">
"""

    if not routers:
        html += """
        <div class="no-data">
            <h2>No Routers Configured</h2>
            <p>No MQ managers have been identified as routers in the current dataset.</p>
            <p>Add entries to <code>input/routers.json</code> to classify MQ managers as routers.</p>
        </div>
"""
    else:
        html += f"""
        <div class="summary">
            <div class="summary-card accent">
                <h3>Total Routers</h3>
                <div class="count">{len(routers)}</div>
            </div>
            <div class="summary-card">
                <h3>Total Inbound</h3>
                <div class="count">{sum(r['inbound'] for r in routers)}</div>
            </div>
            <div class="summary-card">
                <h3>Total Outbound</h3>
                <div class="count">{sum(r['outbound'] for r in routers)}</div>
            </div>
        </div>
"""
        html += _section_open("Router Inventory")
        html += _table_open(["Router Name", "Description", "Organization", "Department", "Inbound", "Outbound", "Total Connections"])
        rows = []
        for r in routers:
            total = r['inbound'] + r['outbound']
            rows.append(f"""
                    <tr>
                        <td><strong>{r['name']}</strong></td>
                        <td>{r['description'] or '—'}</td>
                        <td>{r['organization']}</td>
                        <td>{r['department']}</td>
                        <td>{r['inbound']}</td>
                        <td>{r['outbound']}</td>
                        <td><strong>{total}</strong></td>
                    </tr>""")
        html += "".join(rows)
        html += _table_close() + _section_close()

    html += """
    </div>
"""
    return html


# ---------------------------------------------------------------------------
# HTML fragment helpers (match the standalone report structure exactly)
# ---------------------------------------------------------------------------

def _section_open(title: str) -> str:
    return f"""
        <div class="section">
            <h2>{title}</h2>
"""

def _section_close() -> str:
    return """        </div>
"""

def _table_open(headers: list) -> str:
    ths = ''.join(f'<th>{h}</th>' for h in headers)
    return f"""            <table>
                <thead><tr>{ths}</tr></thead>
                <tbody>
"""

def _table_close() -> str:
    return """                </tbody>
            </table>
"""

def _details_open(label: str) -> str:
    return f"""            <details open>
            <summary>{label}</summary>
            <div class="detail-body">
"""

def _details_close() -> str:
    return """            </div>
            </details>
"""


# ──────────────────────────────────────────────────────────────────────────────
# Open-Architecture wrapper
# ──────────────────────────────────────────────────────────────────────────────

from core.interfaces import Generator, PipelineContext  # noqa: E402
from core.registry import PluginRegistry                # noqa: E402


@PluginRegistry.register(order=10.5)
class ConsolidatedReportStep(Generator):
    """Combine change detection + gateway analytics into one HTML report (step 10.5).

    Reads:  context.changes, context.gateway_analytics, context.enriched_data
    Writes: context.consolidated_report_file  (Path to the generated HTML)
    """

    name             = "Consolidated Report"
    abort_on_failure = False

    def execute(self, context: PipelineContext) -> None:
        config    = context.config
        timestamp = context.timestamp
        try:
            output = config.REPORTS_DIR / f"consolidated_report_{timestamp}.html"
            generate_consolidated_report(
                changes            = context.changes,
                gateway_analytics  = context.gateway_analytics,
                output_file        = output,
                current_timestamp  = timestamp,
                baseline_timestamp = context.baseline_time_str,
                enriched_data      = context.enriched_data,
            )
            context.consolidated_report_file = output
            logger.info(f"✓ Consolidated report: {output}")
        except Exception as exc:
            context.record_error(self.name, exc)



