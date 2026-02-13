
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
from utils.logging_config import get_logger

logger = get_logger("processors.change_detector")


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

        Raises:
            ValueError: If current_data or baseline_data is not a dictionary
        """
        if not isinstance(current_data, dict):
            raise ValueError(f"current_data must be a dict, got {type(current_data).__name__}")
        if not isinstance(baseline_data, dict):
            raise ValueError(f"baseline_data must be a dict, got {type(baseline_data).__name__}")

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
    """Generate an HTML diff report with rich UI."""
    from utils.report_styles import get_report_css, get_report_js

    summary = changes['summary']
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MQ CMDB Change Report</title>
    <style>{get_report_css('#3498db')}</style>
</head>
<body>
    <div class="hero">
        <h1>MQ CMDB Change Detection Report</h1>
        <p>Baseline vs. current snapshot comparison</p>
        <div class="meta">
            <span>Baseline: {baseline_timestamp}</span>
            <span>Current: {current_timestamp}</span>
            <span>Generated: {generated_at}</span>
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
        html += """
        <div class="section">
            <h2>MQ Managers Added</h2>
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
            <h2>MQ Managers Removed</h2>
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
            <h2>MQ Managers Modified</h2>
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
                changes_text.append(f"{field}: {change['old']} &rarr; {change['new']}")
            html += f"""
                    <tr>
                        <td><strong>{mgr['name']}</strong></td>
                        <td class="change-detail">{'<br>'.join(changes_text)}</td>
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
            <h2>Connections Added</h2>
            <table>
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Target</th>
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
            <h2>Connections Removed</h2>
            <table>
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Target</th>
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
            <h2>Gateway Changes</h2>
"""
        if changes['gateways']['added']:
            html += """
            <details open>
            <summary>Added Gateways</summary>
            <div class="detail-body">
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
            </div>
            </details>
"""
        if changes['gateways']['removed']:
            html += """
            <details open>
            <summary>Removed Gateways</summary>
            <div class="detail-body">
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
            </div>
            </details>
"""
        if changes['gateways']['modified']:
            html += """
            <details open>
            <summary>Modified Gateway Scopes</summary>
            <div class="detail-body">
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
            </div>
            </details>
"""
        html += """
        </div>
"""

    # Queue Count Changes
    if changes['queue_counts']:
        html += """
        <div class="section">
            <h2>Significant Queue Count Changes (&gt;20%)</h2>
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
        html += """
                </tbody>
            </table>
        </div>
"""

    # No changes message
    if summary['total_changes'] == 0:
        html += """
        <div class="no-changes">
            <h2>No Changes Detected</h2>
            <p>The current MQ CMDB data is identical to the baseline.</p>
        </div>
"""

    html += f"""
    </div>
    <script>{get_report_js()}</script>
</body>
</html>
"""

    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"✓ Change report generated: {output_file}")

