
"""
Consolidated Report Generator

Combines the Change Detection and Gateway Analytics reports into a single
HTML document with tab navigation, so both views are accessible from one file.
Uses the shared report_styles.py for consistent look and feel.
"""

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from utils.logging_config import get_logger

logger = get_logger("utils.report_consolidator")


def generate_consolidated_report(
    changes: Optional[Dict],
    gateway_analytics: Optional[Dict],
    output_file: Path,
    current_timestamp: str,
    baseline_timestamp: str = None,
    data_augmentation: Optional[List[Dict]] = None,
) -> Path:
    """
    Generate a single HTML report combining change detection, gateway analytics,
    and data augmentation views.

    Each report appears as a separate tab with navigation at the top.
    Gracefully handles missing data (no baseline, no gateways, no augmentation data).

    Args:
        changes: Change detection dict from ChangeDetector.compare(), or None
        gateway_analytics: Gateway analytics dict from GatewayAnalyzer.analyze(), or None
        output_file: Path to write the consolidated HTML file
        current_timestamp: Current pipeline run timestamp
        baseline_timestamp: Baseline timestamp string, or None if no baseline
        data_augmentation: List of augmentation records from data_augmentation.json, or None

    Returns:
        Path to the generated file
    """
    from utils.report_styles import get_report_css, get_report_js

    report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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
        <button class="tab-btn" id="btn-augmentation" onclick="showTab('augmentation')">Data Augmentation</button>
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

    <div id="tab-augmentation" class="tab-pane">
"""

    # -- Data Augmentation tab --
    html += _build_augmentation_tab(data_augmentation, report_time)

    html += f"""
    </div>

    <script>{get_report_js()}

    /* Tab switching */
    function showTab(tab) {{
        document.querySelectorAll('.tab-pane').forEach(function(el) {{ el.classList.remove('active'); }});
        document.querySelectorAll('.tab-btn').forEach(function(el) {{ el.classList.remove('active'); }});
        document.getElementById('tab-' + tab).classList.add('active');
        document.getElementById('btn-' + tab).classList.add('active');

        /* Swap accent colour so section borders and cards match the active tab */
        var colors = {{ 'changes': '#3498db', 'gateways': '#9b59b6', 'augmentation': '#16a085' }};
        document.documentElement.style.setProperty('--accent', colors[tab] || '#3498db');
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

    summary = changes['summary']

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
                <div class="count">{summary['total_changes']}</div>
            </div>
            <div class="summary-card added">
                <h3>Managers Added</h3>
                <div class="count">{summary['mqmanagers_added']}</div>
            </div>
            <div class="summary-card removed">
                <h3>Managers Removed</h3>
                <div class="count">{summary['mqmanagers_removed']}</div>
            </div>
            <div class="summary-card modified">
                <h3>Managers Modified</h3>
                <div class="count">{summary['mqmanagers_modified']}</div>
            </div>
            <div class="summary-card added">
                <h3>Connections Added</h3>
                <div class="count">{summary['connections_added']}</div>
            </div>
            <div class="summary-card removed">
                <h3>Connections Removed</h3>
                <div class="count">{summary['connections_removed']}</div>
            </div>
        </div>
"""

    # MQ Managers Added
    if changes['mqmanagers']['added']:
        html += _section_open("MQ Managers Added")
        html += _table_open(["MQ Manager", "Organization", "Department", "Application", "Type"])
        for mgr in changes['mqmanagers']['added']:
            gateway_badge = '<span class="badge badge-gateway">Gateway</span>' if mgr['is_gateway'] else ''
            html += f"""
                    <tr>
                        <td><strong>{mgr['name']}</strong></td>
                        <td>{mgr['organization']}</td>
                        <td>{mgr['department']}</td>
                        <td>{mgr['application']}</td>
                        <td>{gateway_badge}</td>
                    </tr>
"""
        html += _table_close() + _section_close()

    # MQ Managers Removed
    if changes['mqmanagers']['removed']:
        html += _section_open("MQ Managers Removed")
        html += _table_open(["MQ Manager", "Organization", "Department", "Application"])
        for mgr in changes['mqmanagers']['removed']:
            html += f"""
                    <tr>
                        <td><strong>{mgr['name']}</strong></td>
                        <td>{mgr['organization']}</td>
                        <td>{mgr['department']}</td>
                        <td>{mgr['application']}</td>
                    </tr>
"""
        html += _table_close() + _section_close()

    # MQ Managers Modified
    if changes['mqmanagers']['modified']:
        html += _section_open("MQ Managers Modified")
        html += _table_open(["MQ Manager", "Changes"])
        for mgr in changes['mqmanagers']['modified']:
            changes_text = '<br>'.join(
                f"{field}: {c['old']} &rarr; {c['new']}" for field, c in mgr['changes'].items()
            )
            html += f"""
                    <tr>
                        <td><strong>{mgr['name']}</strong></td>
                        <td class="change-detail">{changes_text}</td>
                    </tr>
"""
        html += _table_close() + _section_close()

    # Connections Added
    if changes['connections']['added']:
        html += _section_open("Connections Added")
        html += _table_open(["Source", "Target", "Source Org", "Target Org"])
        for conn in changes['connections']['added']:
            html += f"""
                    <tr>
                        <td>{conn['source']}</td>
                        <td>{conn['target']}</td>
                        <td>{conn['source_org']}</td>
                        <td>{conn['target_org']}</td>
                    </tr>
"""
        html += _table_close() + _section_close()

    # Connections Removed
    if changes['connections']['removed']:
        html += _section_open("Connections Removed")
        html += _table_open(["Source", "Target", "Source Org", "Target Org"])
        for conn in changes['connections']['removed']:
            html += f"""
                    <tr>
                        <td>{conn['source']}</td>
                        <td>{conn['target']}</td>
                        <td>{conn['source_org']}</td>
                        <td>{conn['target_org']}</td>
                    </tr>
"""
        html += _table_close() + _section_close()

    # Gateway Changes
    if changes['gateways']['added'] or changes['gateways']['removed'] or changes['gateways']['modified']:
        html += _section_open("Gateway Changes")

        if changes['gateways']['added']:
            html += _details_open("Added Gateways")
            html += _table_open(["Gateway Name", "Scope", "Organization", "Department"])
            for gw in changes['gateways']['added']:
                html += f"""
                    <tr>
                        <td><strong>{gw['name']}</strong></td>
                        <td><span class="badge badge-gateway">{gw['scope']}</span></td>
                        <td>{gw['organization']}</td>
                        <td>{gw['department']}</td>
                    </tr>
"""
            html += _table_close() + _details_close()

        if changes['gateways']['removed']:
            html += _details_open("Removed Gateways")
            html += _table_open(["Gateway Name", "Scope", "Organization"])
            for gw in changes['gateways']['removed']:
                html += f"""
                    <tr>
                        <td><strong>{gw['name']}</strong></td>
                        <td><span class="badge badge-gateway">{gw['scope']}</span></td>
                        <td>{gw['organization']}</td>
                    </tr>
"""
            html += _table_close() + _details_close()

        if changes['gateways']['modified']:
            html += _details_open("Modified Gateway Scopes")
            html += _table_open(["Gateway Name", "Old Scope", "New Scope"])
            for gw in changes['gateways']['modified']:
                html += f"""
                    <tr>
                        <td><strong>{gw['name']}</strong></td>
                        <td>{gw['old_scope']}</td>
                        <td>{gw['new_scope']}</td>
                    </tr>
"""
            html += _table_close() + _details_close()

        html += _section_close()

    # Queue Count Changes
    if changes['queue_counts']:
        html += _section_open("Significant Queue Count Changes (&gt;20%)")
        html += _table_open(["MQ Manager", "Queue Type", "Old Count", "New Count", "Change %"])
        for qc in changes['queue_counts']:
            direction = "added" if qc['new_count'] > qc['old_count'] else "removed"
            html += f"""
                    <tr>
                        <td>{qc['mqmanager']}</td>
                        <td>{qc['queue_type']}</td>
                        <td>{qc['old_count']}</td>
                        <td>{qc['new_count']}</td>
                        <td><span class="badge badge-{direction}">{qc['change_percent']}%</span></td>
                    </tr>
"""
        html += _table_close() + _section_close()

    # No changes message
    if summary['total_changes'] == 0:
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

    summary = gateway_analytics['summary']

    # Max load score for CSS bar charts
    all_loads = (gateway_analytics['load_distribution']['internal_gateways'] +
                 gateway_analytics['load_distribution']['external_gateways'])
    max_load = max((ld['load_score'] for ld in all_loads), default=1) or 1

    html = f"""
    <div class="hero" style="background: linear-gradient(135deg, #1e293b 0%, #334155 50%, #9b59b6 100%);">
        <h1>Gateway Analytics Report</h1>
        <p>Traffic patterns, dependencies, and redundancy analysis</p>
        <div class="meta">
            <span>Generated: {report_time}</span>
            <span>Gateways analyzed: {summary['total_gateways']}</span>
        </div>
    </div>

    <div class="container">
        <div class="summary">
            <div class="summary-card accent">
                <h3>Total Gateways</h3>
                <div class="count">{summary['total_gateways']}</div>
            </div>
            <div class="summary-card internal">
                <h3>Internal</h3>
                <div class="count">{summary['internal_gateways']}</div>
            </div>
            <div class="summary-card external">
                <h3>External</h3>
                <div class="count">{summary['external_gateways']}</div>
            </div>
            <div class="summary-card">
                <h3>Total Connections</h3>
                <div class="count">{summary['total_gateway_connections']}</div>
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

    for gw_name, traffic in sorted(gateway_analytics['gateway_traffic'].items(),
                                     key=lambda x: x[1]['total_connections'], reverse=True):
        scope_class = traffic['scope'].lower() if traffic['scope'] else 'internal'
        scope_badge = f'<span class="badge badge-{scope_class}">{traffic["scope"]}</span>'
        html += f"""
                    <tr>
                        <td><strong>{gw_name}</strong></td>
                        <td>{scope_badge}</td>
                        <td>{traffic['organization']}</td>
                        <td>{traffic['inbound_connections']}</td>
                        <td>{traffic['outbound_connections']}</td>
                        <td><strong>{traffic['total_connections']}</strong></td>
                        <td>{traffic['connected_organizations']}</td>
                        <td>{traffic['connected_departments']}</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
        </div>
"""

    # Redundancy Analysis
    redundancy = gateway_analytics['redundancy_analysis']
    if redundancy['spof_count'] > 0:
        html += f"""
        <div class="alert alert-danger">
            <h3>Single Points of Failure Detected</h3>
            <p>Found <strong>{redundancy['spof_count']}</strong> critical routes with no gateway redundancy.</p>
        </div>
"""
        html += _section_open("Single Points of Failure")
        html += _table_open(["Route", "Type", "Gateway", "Connections"])
        for spof in redundancy['single_points_of_failure']:
            html += f"""
                    <tr>
                        <td>{spof['route']}</td>
                        <td>{spof['type']}</td>
                        <td><strong>{spof['gateway']}</strong></td>
                        <td>{spof['connection_count']}</td>
                    </tr>
"""
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

    if gateway_analytics['load_distribution']['internal_gateways']:
        html += _details_open("Internal Gateways")
        html += _table_open(["Gateway", "Connections", "Queues", "Load Score"])
        for ld in gateway_analytics['load_distribution']['internal_gateways']:
            bar_pct = int(ld['load_score'] / max_load * 100)
            html += f"""
                    <tr>
                        <td>{ld['gateway']}</td>
                        <td>{ld['connections']}</td>
                        <td>{ld['queues']}</td>
                        <td>
                            <div class="bar-wrap">
                                <div class="bar" style="width:{bar_pct}%"></div>
                                <span class="bar-label">{ld['load_score']}</span>
                            </div>
                        </td>
                    </tr>
"""
        html += _table_close() + _details_close()

    if gateway_analytics['load_distribution']['external_gateways']:
        html += _details_open("External Gateways")
        html += _table_open(["Gateway", "Connections", "Queues", "Load Score"])
        for ld in gateway_analytics['load_distribution']['external_gateways']:
            bar_pct = int(ld['load_score'] / max_load * 100)
            html += f"""
                    <tr>
                        <td>{ld['gateway']}</td>
                        <td>{ld['connections']}</td>
                        <td>{ld['queues']}</td>
                        <td>
                            <div class="bar-wrap">
                                <div class="bar" style="width:{bar_pct}%"></div>
                                <span class="bar-label">{ld['load_score']}</span>
                            </div>
                        </td>
                    </tr>
"""
        html += _table_close() + _details_close()

    html += _section_close()

    # Organization Connectivity Matrix
    html += _section_open("Organization Connectivity Matrix")
    html += _table_open(["Organization Route", "Gateways", "Connections", "Redundancy"])
    for route, data in sorted(gateway_analytics['org_connectivity'].items(),
                                key=lambda x: x[1]['connection_count'], reverse=True):
        redundancy_badge = ('<span class="badge badge-ok">Yes</span>'
                            if len(data['gateways']) > 1
                            else '<span class="badge badge-warning">No</span>')
        html += f"""
                    <tr>
                        <td>{route}</td>
                        <td>{', '.join(data['gateways'])}</td>
                        <td>{data['connection_count']}</td>
                        <td>{redundancy_badge}</td>
                    </tr>
"""
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
# Data Augmentation tab
# ---------------------------------------------------------------------------

def _build_augmentation_tab(data_augmentation, report_time):
    """Build the Data Augmentation tab content."""
    if not data_augmentation:
        return """
        <div class="no-data">
            <h2>No Data Augmentation Records</h2>
            <p>The <code>input/data_augmentation.json</code> file is empty or was not found.</p>
            <p>Add records with fields: field_name, asset, extrainfo, MQmanager, Application, directorate, Org, Validity.</p>
        </div>
"""

    html = f"""
    <div class="hero" style="background: linear-gradient(135deg, #1e293b 0%, #334155 50%, #16a085 100%);">
        <h1>Data Augmentation Report</h1>
        <p>Supplementary data for outbound_extra and inbound_extra connections</p>
        <div class="meta">
            <span>Generated: {report_time}</span>
            <span>Records: {len(data_augmentation)}</span>
        </div>
    </div>

    <div class="container">
        <div class="summary">
            <div class="summary-card accent">
                <h3>Total Records</h3>
                <div class="count">{len(data_augmentation)}</div>
            </div>
            <div class="summary-card added">
                <h3>Valid</h3>
                <div class="count">{sum(1 for r in data_augmentation if str(r.get('Validity', '')).upper() in ('YES', 'VALID', 'TRUE', 'Y'))}</div>
            </div>
            <div class="summary-card removed">
                <h3>Invalid</h3>
                <div class="count">{sum(1 for r in data_augmentation if str(r.get('Validity', '')).upper() in ('NO', 'INVALID', 'FALSE', 'N'))}</div>
            </div>
            <div class="summary-card modified">
                <h3>Pending Review</h3>
                <div class="count">{sum(1 for r in data_augmentation if str(r.get('Validity', '')).strip() == '')}</div>
            </div>
        </div>
"""

    html += _section_open("Data Augmentation Records")
    html += _table_open(["Field Name", "Asset", "Extra Info", "MQ Manager", "Application", "Directorate", "Org", "Validity"])

    for record in data_augmentation:
        validity = str(record.get('Validity', '')).strip()
        if validity.upper() in ('YES', 'VALID', 'TRUE', 'Y'):
            validity_badge = f'<span class="badge badge-ok">{validity}</span>'
        elif validity.upper() in ('NO', 'INVALID', 'FALSE', 'N'):
            validity_badge = f'<span class="badge badge-warning">{validity}</span>'
        else:
            validity_badge = f'<span class="badge badge-modified">{validity or "Pending"}</span>'

        html += f"""
                    <tr>
                        <td><strong>{record.get('field_name', '')}</strong></td>
                        <td>{record.get('asset', '')}</td>
                        <td>{record.get('extrainfo', '')}</td>
                        <td>{record.get('MQmanager', '')}</td>
                        <td>{record.get('Application', '')}</td>
                        <td>{record.get('directorate', '')}</td>
                        <td>{record.get('Org', '')}</td>
                        <td>{validity_badge}</td>
                    </tr>
"""

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