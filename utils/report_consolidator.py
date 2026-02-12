"""
Consolidated Report Generator

Combines the Change Detection and Gateway Analytics reports into a single
HTML document with tab navigation, so both views are accessible from one file.
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
    report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MQ CMDB Consolidated Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}

        /* Navigation bar */
        .nav-bar {{
            position: sticky;
            top: 0;
            z-index: 100;
            background-color: #2c3e50;
            padding: 0 20px;
            display: flex;
            align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}
        .nav-title {{
            color: white;
            font-size: 16px;
            font-weight: 600;
            margin-right: 30px;
            padding: 14px 0;
            white-space: nowrap;
        }}
        .tab-btn {{
            background: none;
            border: none;
            color: #bdc3c7;
            font-size: 14px;
            font-weight: 500;
            padding: 14px 20px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: color 0.2s, border-color 0.2s;
            font-family: inherit;
        }}
        .tab-btn:hover {{
            color: white;
        }}
        .tab-btn.active-changes {{
            color: white;
            border-bottom-color: #3498db;
        }}
        .tab-btn.active-gateways {{
            color: white;
            border-bottom-color: #9b59b6;
        }}

        /* Tab content */
        .tab-content {{
            display: none;
            padding: 20px;
        }}
        .tab-content.active {{
            display: block;
        }}

        /* Shared layout */
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header-info {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .timestamp {{
            font-family: monospace;
            color: #555;
        }}

        /* Summary cards */
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card.added {{ background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%); }}
        .summary-card.removed {{ background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); }}
        .summary-card.modified {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .summary-card.internal {{ background: linear-gradient(135deg, #ff9800 0%, #ff5722 100%); }}
        .summary-card.external {{ background: linear-gradient(135deg, #00bcd4 0%, #009688 100%); }}
        .summary-card.purple {{ background: linear-gradient(135deg, #9b59b6 0%, #e91e63 100%); }}
        .summary-card h3 {{ margin: 0 0 10px 0; font-size: 14px; }}
        .summary-card .count {{ font-size: 36px; font-weight: bold; }}

        /* Section headings */
        .section {{
            margin-bottom: 30px;
        }}
        .section-blue h2 {{
            color: #34495e;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }}
        .section-purple h2 {{
            color: #34495e;
            border-left: 4px solid #9b59b6;
            padding-left: 10px;
        }}
        h1.page-title-blue {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h1.page-title-purple {{
            color: #2c3e50;
            border-bottom: 3px solid #9b59b6;
            padding-bottom: 10px;
        }}
        h2.section-heading-purple {{
            color: #34495e;
            border-left: 4px solid #9b59b6;
            padding-left: 10px;
            margin-top: 30px;
        }}

        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        .table-blue th {{
            background-color: #3498db;
            color: white;
            font-weight: 600;
        }}
        .table-purple th {{
            background-color: #9b59b6;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}

        /* Badges */
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge-added {{ background-color: #27ae60; color: white; }}
        .badge-removed {{ background-color: #e74c3c; color: white; }}
        .badge-modified {{ background-color: #f39c12; color: white; }}
        .badge-gateway {{ background-color: #9b59b6; color: white; }}
        .badge-internal {{ background-color: #ff9800; color: white; }}
        .badge-external {{ background-color: #00bcd4; color: white; }}
        .badge-warning {{ background-color: #e74c3c; color: white; }}
        .badge-ok {{ background-color: #27ae60; color: white; }}

        /* Alerts */
        .alert {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .alert-danger {{
            background-color: #f8d7da;
            border-left-color: #dc3545;
        }}

        /* Misc */
        .no-changes {{
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
            font-style: italic;
        }}
        .change-detail {{
            font-size: 12px;
            color: #7f8c8d;
        }}
        .no-data {{
            text-align: center;
            padding: 60px 20px;
            color: #95a5a6;
        }}
        .no-data h2 {{
            border: none;
            color: #95a5a6;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 20px;
            color: #95a5a6;
            font-size: 12px;
            margin-top: 30px;
            border-top: 1px solid #ecf0f1;
        }}
    </style>
</head>
<body>
    <div class="nav-bar">
        <span class="nav-title">MQ CMDB Report</span>
        <button class="tab-btn active-changes" id="btn-changes" onclick="showTab('changes')">Change Detection</button>
        <button class="tab-btn" id="btn-gateways" onclick="showTab('gateways')">Gateway Analytics</button>
    </div>

    <div id="tab-changes" class="tab-content active">
        <div class="container">
"""

    # -- Change Detection tab content --
    html += _build_changes_tab(changes, current_timestamp, baseline_timestamp, report_time)

    html += """
            <div class="footer">MQ CMDB Automation System</div>
        </div>
    </div>

    <div id="tab-gateways" class="tab-content">
        <div class="container">
"""

    # -- Gateway Analytics tab content --
    html += _build_gateways_tab(gateway_analytics, report_time)

    html += f"""
            <div class="footer">MQ CMDB Automation System</div>
        </div>
    </div>

    <script>
        function showTab(tab) {{
            document.getElementById('tab-changes').classList.remove('active');
            document.getElementById('tab-gateways').classList.remove('active');
            document.getElementById('btn-changes').className = 'tab-btn';
            document.getElementById('btn-gateways').className = 'tab-btn';

            document.getElementById('tab-' + tab).classList.add('active');
            if (tab === 'changes') {{
                document.getElementById('btn-changes').className = 'tab-btn active-changes';
            }} else {{
                document.getElementById('btn-gateways').className = 'tab-btn active-gateways';
            }}
        }}
    </script>
</body>
</html>
"""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"✓ Consolidated report generated: {output_file}")
    return output_file


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
            <h1 class="page-title-blue">Change Detection Report</h1>

            <div class="header-info">
                <p><strong>Baseline:</strong> <span class="timestamp">{baseline_timestamp or 'N/A'}</span></p>
                <p><strong>Current:</strong> <span class="timestamp">{current_timestamp}</span></p>
                <p><strong>Report Generated:</strong> <span class="timestamp">{report_time}</span></p>
            </div>

            <div class="summary">
                <div class="summary-card">
                    <h3>Total Changes</h3>
                    <div class="count">{summary['total_changes']}</div>
                </div>
                <div class="summary-card added">
                    <h3>MQ Managers Added</h3>
                    <div class="count">{summary['mqmanagers_added']}</div>
                </div>
                <div class="summary-card removed">
                    <h3>MQ Managers Removed</h3>
                    <div class="count">{summary['mqmanagers_removed']}</div>
                </div>
                <div class="summary-card modified">
                    <h3>MQ Managers Modified</h3>
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
        html += _table_section_blue("MQ Managers Added",
            ["MQ Manager", "Organization", "Department", "Application", "Type"],
            [[f"<strong>{m['name']}</strong>", m['organization'], m['department'], m['application'],
              '<span class="badge badge-gateway">Gateway</span>' if m['is_gateway'] else '']
             for m in changes['mqmanagers']['added']])

    # MQ Managers Removed
    if changes['mqmanagers']['removed']:
        html += _table_section_blue("MQ Managers Removed",
            ["MQ Manager", "Organization", "Department", "Application"],
            [[f"<strong>{m['name']}</strong>", m['organization'], m['department'], m['application']]
             for m in changes['mqmanagers']['removed']])

    # MQ Managers Modified
    if changes['mqmanagers']['modified']:
        rows = []
        for mgr in changes['mqmanagers']['modified']:
            changes_text = ', '.join(
                f"{field}: {c['old']} &rarr; {c['new']}" for field, c in mgr['changes'].items()
            )
            rows.append([f"<strong>{mgr['name']}</strong>", f'<span class="change-detail">{changes_text}</span>'])
        html += _table_section_blue("MQ Managers Modified", ["MQ Manager", "Changes"], rows)

    # Connections Added
    if changes['connections']['added']:
        html += _table_section_blue("Connections Added",
            ["Source MQ Manager", "Target MQ Manager", "Source Org", "Target Org"],
            [[c['source'], c['target'], c['source_org'], c['target_org']]
             for c in changes['connections']['added']])

    # Connections Removed
    if changes['connections']['removed']:
        html += _table_section_blue("Connections Removed",
            ["Source MQ Manager", "Target MQ Manager", "Source Org", "Target Org"],
            [[c['source'], c['target'], c['source_org'], c['target_org']]
             for c in changes['connections']['removed']])

    # Gateway Changes
    if changes['gateways']['added'] or changes['gateways']['removed'] or changes['gateways']['modified']:
        html += '            <div class="section section-blue"><h2>Gateway Changes</h2>\n'

        if changes['gateways']['added']:
            html += '            <h3>Added Gateways</h3>\n'
            html += _simple_table_blue(
                ["Gateway Name", "Scope", "Organization", "Department"],
                [[f"<strong>{g['name']}</strong>", f'<span class="badge badge-gateway">{g["scope"]}</span>',
                  g['organization'], g['department']]
                 for g in changes['gateways']['added']])

        if changes['gateways']['removed']:
            html += '            <h3>Removed Gateways</h3>\n'
            html += _simple_table_blue(
                ["Gateway Name", "Scope", "Organization"],
                [[f"<strong>{g['name']}</strong>", f'<span class="badge badge-gateway">{g["scope"]}</span>',
                  g['organization']]
                 for g in changes['gateways']['removed']])

        if changes['gateways']['modified']:
            html += '            <h3>Modified Gateway Scopes</h3>\n'
            html += _simple_table_blue(
                ["Gateway Name", "Old Scope", "New Scope"],
                [[f"<strong>{g['name']}</strong>", g['old_scope'], g['new_scope']]
                 for g in changes['gateways']['modified']])

        html += '            </div>\n'

    # Queue Count Changes
    if changes['queue_counts']:
        html += _table_section_blue("Significant Queue Count Changes (&gt;20%)",
            ["MQ Manager", "Queue Type", "Old Count", "New Count", "Change %"],
            [[q['mqmanager'], q['queue_type'], str(q['old_count']), str(q['new_count']), f"{q['change_percent']}%"]
             for q in changes['queue_counts']])

    # No changes message
    if summary['total_changes'] == 0:
        html += """
            <div class="no-changes">
                <h2>No Changes Detected</h2>
                <p>The current MQ CMDB data is identical to the baseline.</p>
            </div>
"""

    return html


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

    html = f"""
            <h1 class="page-title-purple">Gateway Analytics Report</h1>
            <p><strong>Generated:</strong> <span class="timestamp">{report_time}</span></p>

            <div class="summary">
                <div class="summary-card purple">
                    <h3>Total Gateways</h3>
                    <div class="count">{summary['total_gateways']}</div>
                </div>
                <div class="summary-card internal">
                    <h3>Internal Gateways</h3>
                    <div class="count">{summary['internal_gateways']}</div>
                </div>
                <div class="summary-card external">
                    <h3>External Gateways</h3>
                    <div class="count">{summary['external_gateways']}</div>
                </div>
                <div class="summary-card purple">
                    <h3>Total Connections</h3>
                    <div class="count">{summary['total_gateway_connections']}</div>
                </div>
            </div>
"""

    # Gateway Traffic Overview
    html += '            <h2 class="section-heading-purple">Gateway Traffic Overview</h2>\n'
    traffic_rows = []
    for gw_name, traffic in sorted(gateway_analytics['gateway_traffic'].items(),
                                     key=lambda x: x[1]['total_connections'], reverse=True):
        scope_badge = f'<span class="badge badge-{traffic["scope"].lower()}">{traffic["scope"]}</span>'
        traffic_rows.append([
            f"<strong>{gw_name}</strong>", scope_badge, traffic['organization'],
            str(traffic['inbound_connections']), str(traffic['outbound_connections']),
            f"<strong>{traffic['total_connections']}</strong>",
            str(traffic['connected_organizations']), str(traffic['connected_departments']),
        ])
    html += _simple_table_purple(
        ["Gateway", "Scope", "Organization", "Inbound", "Outbound", "Total", "Connected Orgs", "Connected Depts"],
        traffic_rows)

    # Redundancy Analysis
    redundancy = gateway_analytics['redundancy_analysis']
    if redundancy['spof_count'] > 0:
        html += f"""
            <div class="alert alert-danger">
                <h2 class="section-heading-purple">Single Points of Failure Detected</h2>
                <p>Found <strong>{redundancy['spof_count']}</strong> critical routes with no gateway redundancy:</p>
"""
        html += _simple_table_purple(
            ["Route", "Type", "Gateway", "Connections"],
            [[s['route'], s['type'], f"<strong>{s['gateway']}</strong>", str(s['connection_count'])]
             for s in redundancy['single_points_of_failure']])
        html += '            </div>\n'
    else:
        html += """
            <div class="alert">
                <h2 class="section-heading-purple">Gateway Redundancy</h2>
                <p>All critical routes have redundant gateways configured.</p>
            </div>
"""

    # Load Distribution - Internal
    html += '            <h2 class="section-heading-purple">Load Distribution</h2>\n'
    html += '            <h3>Internal Gateways</h3>\n'
    html += _simple_table_purple(
        ["Gateway", "Connections", "Queues", "Load Score"],
        [[ld['gateway'], str(ld['connections']), str(ld['queues']), f"<strong>{ld['load_score']}</strong>"]
         for ld in gateway_analytics['load_distribution']['internal_gateways']])

    # Load Distribution - External
    html += '            <h3>External Gateways</h3>\n'
    html += _simple_table_purple(
        ["Gateway", "Connections", "Queues", "Load Score"],
        [[ld['gateway'], str(ld['connections']), str(ld['queues']), f"<strong>{ld['load_score']}</strong>"]
         for ld in gateway_analytics['load_distribution']['external_gateways']])

    # Organization Connectivity Matrix
    html += '            <h2 class="section-heading-purple">Organization Connectivity Matrix</h2>\n'
    conn_rows = []
    for route, data in sorted(gateway_analytics['org_connectivity'].items(),
                                key=lambda x: x[1]['connection_count'], reverse=True):
        redundancy_badge = ('<span class="badge badge-ok">Yes</span>'
                            if len(data['gateways']) > 1
                            else '<span class="badge badge-warning">No</span>')
        conn_rows.append([route, ', '.join(data['gateways']), str(data['connection_count']), redundancy_badge])
    html += _simple_table_purple(
        ["Organization Route", "Gateways", "Connections", "Redundancy"],
        conn_rows)

    return html


# -- Table helpers --

def _table_section_blue(title, headers, rows):
    """Build a section with a blue-themed table."""
    html = f'            <div class="section section-blue"><h2>{title}</h2>\n'
    html += _simple_table_blue(headers, rows)
    html += '            </div>\n'
    return html


def _simple_table_blue(headers, rows):
    """Build a blue-themed table."""
    return _build_table("table-blue", headers, rows)


def _simple_table_purple(headers, rows):
    """Build a purple-themed table."""
    return _build_table("table-purple", headers, rows)


def _build_table(css_class, headers, rows):
    """Build an HTML table with the given class, headers, and rows."""
    html = f'            <table class="{css_class}">\n'
    html += '                <thead><tr>'
    for h in headers:
        html += f'<th>{h}</th>'
    html += '</tr></thead>\n'
    html += '                <tbody>\n'
    for row in rows:
        html += '                    <tr>'
        for cell in row:
            html += f'<td>{cell}</td>'
        html += '</tr>\n'
    html += '                </tbody>\n'
    html += '            </table>\n'
    return html
