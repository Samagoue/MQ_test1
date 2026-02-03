"""
Change Detection and Diff Report Generator

Compares current MQ CMDB data against a baseline to detect changes:
- New/removed MQ managers
- New/removed connections
- Changes in queue counts
- Gateway configuration changes
"""

from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime
from utils.file_io import load_json, save_json


class ChangeDetector:
    """Detect and report changes between MQ CMDB snapshots."""

    def __init__(self):
        self.changes = {
            'mqmanagers': {'added': [], 'removed': [], 'modified': []},
            'connections': {'added': [], 'removed': []},
            'gateways': {'added': [], 'removed': [], 'modified': []},
            'queue_counts': [],
            'summary': {}
        }

    def compare(self, current_data: Dict, baseline_data: Dict) -> Dict:
        """
        Compare current data against baseline and detect changes.

        Args:
            current_data: Current processed MQ CMDB data
            baseline_data: Previous baseline data

        Returns:
            Dictionary of detected changes
        """
        # Extract MQ managers from both datasets
        current_mqmgrs = self._extract_mqmanagers(current_data)
        baseline_mqmgrs = self._extract_mqmanagers(baseline_data)

        # Detect MQ manager changes
        self._detect_mqmanager_changes(current_mqmgrs, baseline_mqmgrs)

        # Detect connection changes
        self._detect_connection_changes(current_mqmgrs, baseline_mqmgrs)

        # Detect gateway changes
        self._detect_gateway_changes(current_mqmgrs, baseline_mqmgrs)

        # Detect queue count changes
        self._detect_queue_count_changes(current_mqmgrs, baseline_mqmgrs)

        # Generate summary
        self._generate_summary()

        return self.changes

    def _extract_mqmanagers(self, data: Dict) -> Dict[str, Dict]:
        """Extract all MQ managers from hierarchical data structure."""
        mqmanagers = {}

        for org_name, org_data in data.items():
            if not isinstance(org_data, dict) or '_departments' not in org_data:
                continue

            for dept_name, dept_data in org_data['_departments'].items():
                for biz_ownr, applications in dept_data.items():
                    for app_name, mqmgr_dict in applications.items():
                        for mqmgr_name, mqmgr_data in mqmgr_dict.items():
                            mqmanagers[mqmgr_name] = mqmgr_data

        return mqmanagers

    def _detect_mqmanager_changes(self, current: Dict, baseline: Dict):
        """Detect added, removed, and modified MQ managers."""
        current_names = set(current.keys())
        baseline_names = set(baseline.keys())

        # Added MQ managers
        added = current_names - baseline_names
        for name in added:
            self.changes['mqmanagers']['added'].append({
                'name': name,
                'organization': current[name].get('Organization', ''),
                'department': current[name].get('Department', ''),
                'application': current[name].get('Application', ''),
                'is_gateway': current[name].get('IsGateway', False)
            })

        # Removed MQ managers
        removed = baseline_names - current_names
        for name in removed:
            self.changes['mqmanagers']['removed'].append({
                'name': name,
                'organization': baseline[name].get('Organization', ''),
                'department': baseline[name].get('Department', ''),
                'application': baseline[name].get('Application', '')
            })

        # Modified MQ managers (organizational changes)
        common = current_names & baseline_names
        for name in common:
            curr = current[name]
            base = baseline[name]

            changes = {}
            for field in ['Organization', 'Department', 'Biz_Ownr', 'Application']:
                if curr.get(field) != base.get(field):
                    changes[field] = {
                        'old': base.get(field, ''),
                        'new': curr.get(field, '')
                    }

            if changes:
                self.changes['mqmanagers']['modified'].append({
                    'name': name,
                    'changes': changes
                })

    def _detect_connection_changes(self, current: Dict, baseline: Dict):
        """Detect added and removed connections."""
        # Extract all connections from current
        current_connections = set()
        for mqmgr_name, mqmgr_data in current.items():
            for target in mqmgr_data.get('outbound', []):
                current_connections.add((mqmgr_name, target))
            for target in mqmgr_data.get('outbound_extra', []):
                current_connections.add((mqmgr_name, target))

        # Extract all connections from baseline
        baseline_connections = set()
        for mqmgr_name, mqmgr_data in baseline.items():
            for target in mqmgr_data.get('outbound', []):
                baseline_connections.add((mqmgr_name, target))
            for target in mqmgr_data.get('outbound_extra', []):
                baseline_connections.add((mqmgr_name, target))

        # Added connections
        added = current_connections - baseline_connections
        for source, target in added:
            self.changes['connections']['added'].append({
                'source': source,
                'target': target,
                'source_org': current.get(source, {}).get('Organization', ''),
                'target_org': current.get(target, {}).get('Organization', '')
            })

        # Removed connections
        removed = baseline_connections - current_connections
        for source, target in removed:
            self.changes['connections']['removed'].append({
                'source': source,
                'target': target,
                'source_org': baseline.get(source, {}).get('Organization', ''),
                'target_org': baseline.get(target, {}).get('Organization', '')
            })

    def _detect_gateway_changes(self, current: Dict, baseline: Dict):
        """Detect changes in gateway MQ managers."""
        current_gateways = {
            name: data for name, data in current.items()
            if data.get('IsGateway', False)
        }
        baseline_gateways = {
            name: data for name, data in baseline.items()
            if data.get('IsGateway', False)
        }

        current_names = set(current_gateways.keys())
        baseline_names = set(baseline_gateways.keys())

        # Added gateways
        added = current_names - baseline_names
        for name in added:
            self.changes['gateways']['added'].append({
                'name': name,
                'scope': current_gateways[name].get('GatewayScope', ''),
                'organization': current_gateways[name].get('Organization', ''),
                'department': current_gateways[name].get('Department', '')
            })

        # Removed gateways
        removed = baseline_names - current_names
        for name in removed:
            self.changes['gateways']['removed'].append({
                'name': name,
                'scope': baseline_gateways[name].get('GatewayScope', ''),
                'organization': baseline_gateways[name].get('Organization', '')
            })

        # Modified gateway scope
        common = current_names & baseline_names
        for name in common:
            curr_scope = current_gateways[name].get('GatewayScope', '')
            base_scope = baseline_gateways[name].get('GatewayScope', '')
            if curr_scope != base_scope:
                self.changes['gateways']['modified'].append({
                    'name': name,
                    'old_scope': base_scope,
                    'new_scope': curr_scope
                })

    def _detect_queue_count_changes(self, current: Dict, baseline: Dict):
        """Detect significant changes in queue counts."""
        threshold_percent = 20  # Report changes > 20%

        common = set(current.keys()) & set(baseline.keys())
        for name in common:
            curr = current[name]
            base = baseline[name]

            for count_type in ['qlocal_count', 'qremote_count', 'qalias_count']:
                curr_count = curr.get(count_type, 0)
                base_count = base.get(count_type, 0)

                # Skip if both are zero (no change)
                if base_count == 0 and curr_count == 0:
                    continue
                # New queues added (0 -> N)
                elif base_count == 0 and curr_count > 0:
                    change_percent = 100
                # All queues removed (N -> 0)
                elif base_count > 0 and curr_count == 0:
                    change_percent = 100
                # Normal percentage change
                elif base_count > 0:
                    change_percent = abs((curr_count - base_count) / base_count * 100)
                else:
                    continue

                if change_percent >= threshold_percent:
                    self.changes['queue_counts'].append({
                        'mqmanager': name,
                        'queue_type': count_type.replace('_count', ''),
                        'old_count': base_count,
                        'new_count': curr_count,
                        'change_percent': round(change_percent, 1)
                    })

    def _generate_summary(self):
        """Generate summary statistics."""
        self.changes['summary'] = {
            'mqmanagers_added': len(self.changes['mqmanagers']['added']),
            'mqmanagers_removed': len(self.changes['mqmanagers']['removed']),
            'mqmanagers_modified': len(self.changes['mqmanagers']['modified']),
            'connections_added': len(self.changes['connections']['added']),
            'connections_removed': len(self.changes['connections']['removed']),
            'gateways_added': len(self.changes['gateways']['added']),
            'gateways_removed': len(self.changes['gateways']['removed']),
            'gateways_modified': len(self.changes['gateways']['modified']),
            'queue_count_changes': len(self.changes['queue_counts']),
            'total_changes': 0
        }

        # Calculate total changes (including queue count changes)
        self.changes['summary']['total_changes'] = sum([
            self.changes['summary']['mqmanagers_added'],
            self.changes['summary']['mqmanagers_removed'],
            self.changes['summary']['mqmanagers_modified'],
            self.changes['summary']['connections_added'],
            self.changes['summary']['connections_removed'],
            self.changes['summary']['gateways_added'],
            self.changes['summary']['gateways_removed'],
            self.changes['summary']['gateways_modified'],
            self.changes['summary']['queue_count_changes']
        ])


def generate_html_report(changes: Dict, output_file: Path, current_timestamp: str, baseline_timestamp: str):
    """Generate an HTML diff report."""
    summary = changes['summary']

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MQ CMDB Change Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .header-info {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
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
        .summary-card h3 {{ margin: 0 0 10px 0; font-size: 14px; }}
        .summary-card .count {{ font-size: 36px; font-weight: bold; }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h2 {{
            color: #34495e;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }}
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
        th {{
            background-color: #3498db;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
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
        .timestamp {{
            font-family: monospace;
            color: #555;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔄 MQ CMDB Change Detection Report</h1>

        <div class="header-info">
            <p><strong>Baseline:</strong> <span class="timestamp">{baseline_timestamp}</span></p>
            <p><strong>Current:</strong> <span class="timestamp">{current_timestamp}</span></p>
            <p><strong>Report Generated:</strong> <span class="timestamp">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span></p>
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
        html += """
        <div class="section">
            <h2>➕ MQ Managers Added</h2>
            <table>
                <thead>
                    <tr>
                        <th>MQ Manager</th>
                        <th>Organization</th>
                        <th>Department</th>
                        <th>Application</th>
                        <th>Type</th>
                    </tr>
                </thead>
                <tbody>
"""
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
        html += """
                </tbody>
            </table>
        </div>
"""

    # MQ Managers Removed
    if changes['mqmanagers']['removed']:
        html += """
        <div class="section">
            <h2>➖ MQ Managers Removed</h2>
            <table>
                <thead>
                    <tr>
                        <th>MQ Manager</th>
                        <th>Organization</th>
                        <th>Department</th>
                        <th>Application</th>
                    </tr>
                </thead>
                <tbody>
"""
        for mgr in changes['mqmanagers']['removed']:
            html += f"""
                    <tr>
                        <td><strong>{mgr['name']}</strong></td>
                        <td>{mgr['organization']}</td>
                        <td>{mgr['department']}</td>
                        <td>{mgr['application']}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
        </div>
"""

    # MQ Managers Modified
    if changes['mqmanagers']['modified']:
        html += """
        <div class="section">
            <h2>🔄 MQ Managers Modified</h2>
            <table>
                <thead>
                    <tr>
                        <th>MQ Manager</th>
                        <th>Changes</th>
                    </tr>
                </thead>
                <tbody>
"""
        for mgr in changes['mqmanagers']['modified']:
            changes_text = []
            for field, change in mgr['changes'].items():
                changes_text.append(f"{field}: {change['old']} → {change['new']}")
            html += f"""
                    <tr>
                        <td><strong>{mgr['name']}</strong></td>
                        <td class="change-detail">{', '.join(changes_text)}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
        </div>
"""

    # Connections Added
    if changes['connections']['added']:
        html += """
        <div class="section">
            <h2>🔗 Connections Added</h2>
            <table>
                <thead>
                    <tr>
                        <th>Source MQ Manager</th>
                        <th>Target MQ Manager</th>
                        <th>Source Org</th>
                        <th>Target Org</th>
                    </tr>
                </thead>
                <tbody>
"""
        for conn in changes['connections']['added']:
            html += f"""
                    <tr>
                        <td>{conn['source']}</td>
                        <td>{conn['target']}</td>
                        <td>{conn['source_org']}</td>
                        <td>{conn['target_org']}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
        </div>
"""

    # Connections Removed
    if changes['connections']['removed']:
        html += """
        <div class="section">
            <h2>🔗 Connections Removed</h2>
            <table>
                <thead>
                    <tr>
                        <th>Source MQ Manager</th>
                        <th>Target MQ Manager</th>
                        <th>Source Org</th>
                        <th>Target Org</th>
                    </tr>
                </thead>
                <tbody>
"""
        for conn in changes['connections']['removed']:
            html += f"""
                    <tr>
                        <td>{conn['source']}</td>
                        <td>{conn['target']}</td>
                        <td>{conn['source_org']}</td>
                        <td>{conn['target_org']}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
        </div>
"""

    # Gateway Changes
    if changes['gateways']['added'] or changes['gateways']['removed'] or changes['gateways']['modified']:
        html += """
        <div class="section">
            <h2>🔀 Gateway Changes</h2>
"""
        if changes['gateways']['added']:
            html += """
            <h3>Added Gateways</h3>
            <table>
                <thead>
                    <tr>
                        <th>Gateway Name</th>
                        <th>Scope</th>
                        <th>Organization</th>
                        <th>Department</th>
                    </tr>
                </thead>
                <tbody>
"""
            for gw in changes['gateways']['added']:
                html += f"""
                    <tr>
                        <td><strong>{gw['name']}</strong></td>
                        <td><span class="badge badge-gateway">{gw['scope']}</span></td>
                        <td>{gw['organization']}</td>
                        <td>{gw['department']}</td>
                    </tr>
"""
            html += """
                </tbody>
            </table>
"""
        if changes['gateways']['removed']:
            html += """
            <h3>Removed Gateways</h3>
            <table>
                <thead>
                    <tr>
                        <th>Gateway Name</th>
                        <th>Scope</th>
                        <th>Organization</th>
                    </tr>
                </thead>
                <tbody>
"""
            for gw in changes['gateways']['removed']:
                html += f"""
                    <tr>
                        <td><strong>{gw['name']}</strong></td>
                        <td><span class="badge badge-gateway">{gw['scope']}</span></td>
                        <td>{gw['organization']}</td>
                    </tr>
"""
            html += """
                </tbody>
            </table>
"""
        if changes['gateways']['modified']:
            html += """
            <h3>Modified Gateway Scopes</h3>
            <table>
                <thead>
                    <tr>
                        <th>Gateway Name</th>
                        <th>Old Scope</th>
                        <th>New Scope</th>
                    </tr>
                </thead>
                <tbody>
"""
            for gw in changes['gateways']['modified']:
                html += f"""
                    <tr>
                        <td><strong>{gw['name']}</strong></td>
                        <td>{gw['old_scope']}</td>
                        <td>{gw['new_scope']}</td>
                    </tr>
"""
            html += """
                </tbody>
            </table>
"""
        html += """
        </div>
"""

    # Queue Count Changes
    if changes['queue_counts']:
        html += """
        <div class="section">
            <h2>📊 Significant Queue Count Changes (>20%)</h2>
            <table>
                <thead>
                    <tr>
                        <th>MQ Manager</th>
                        <th>Queue Type</th>
                        <th>Old Count</th>
                        <th>New Count</th>
                        <th>Change %</th>
                    </tr>
                </thead>
                <tbody>
"""
        for qc in changes['queue_counts']:
            html += f"""
                    <tr>
                        <td>{qc['mqmanager']}</td>
                        <td>{qc['queue_type']}</td>
                        <td>{qc['old_count']}</td>
                        <td>{qc['new_count']}</td>
                        <td>{qc['change_percent']}%</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
        </div>
"""

    # No changes message
    if summary['total_changes'] == 0:
        html += """
        <div class="no-changes">
            <h2>✅ No Changes Detected</h2>
            <p>The current MQ CMDB data is identical to the baseline.</p>
        </div>
"""

    html += """
    </div>
</body>
</html>
"""

    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ Change report generated: {output_file}")
