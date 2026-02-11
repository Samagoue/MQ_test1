
"""
Gateway Analytics and Insights

Analyzes gateway MQ managers to provide insights on:
- Traffic patterns through gateways
- Department/Organization connectivity via gateways
- Gateway dependencies and redundancy
- Load distribution across gateways
"""

from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from datetime import datetime
from utils.common import iter_mqmanagers
from utils.logging_config import get_logger

logger = get_logger("analytics.gateway")


class GatewayAnalyzer:
    """Analyze gateway usage patterns and generate insights."""

    def __init__(self, enriched_data: Dict):
        """
        Initialize analyzer with enriched MQ CMDB data.

        Args:
            enriched_data: Enriched hierarchical MQ CMDB data

        Raises:
            ValueError: If enriched_data is not a dictionary
        """
        if not isinstance(enriched_data, dict):
            raise ValueError(f"enriched_data must be a dict, got {type(enriched_data).__name__}")
        self.data = enriched_data
        self.gateways = self._extract_gateways()
        self.all_mqmanagers = self._extract_all_mqmanagers()
        self.analytics = {
            'summary': {},
            'gateway_traffic': {},
            'org_connectivity': {},
            'department_connectivity': {},
            'gateway_dependencies': {},
            'load_distribution': {},
            'redundancy_analysis': {}
        }

    def _extract_gateways(self) -> Dict[str, Dict]:
        """Extract all gateway MQ managers from the data."""
        return {
            name: data for name, data in iter_mqmanagers(self.data)
            if data.get('IsGateway', False)
        }

    def _extract_all_mqmanagers(self) -> Dict[str, Dict]:
        """Extract all MQ managers from the data."""
        return dict(iter_mqmanagers(self.data))

    def analyze(self) -> Dict:
        """Run full gateway analysis."""
        self._analyze_summary()
        self._analyze_gateway_traffic()
        self._analyze_org_connectivity()
        self._analyze_department_connectivity()
        self._analyze_dependencies()
        self._analyze_load_distribution()
        self._analyze_redundancy()

        return self.analytics

    def _analyze_summary(self):
        """Generate summary statistics."""
        internal_gateways = [g for g in self.gateways.values() if g.get('GatewayScope') == 'Internal']
        external_gateways = [g for g in self.gateways.values() if g.get('GatewayScope') == 'External']

        self.analytics['summary'] = {
            'total_gateways': len(self.gateways),
            'internal_gateways': len(internal_gateways),
            'external_gateways': len(external_gateways),
            'total_gateway_connections': sum(
                len(g.get('inbound', [])) + len(g.get('outbound', [])) +
                len(g.get('inbound_extra', [])) + len(g.get('outbound_extra', []))
                for g in self.gateways.values()
            )
        }

    def _analyze_gateway_traffic(self):
        """Analyze traffic patterns through each gateway."""
        for gw_name, gw_data in self.gateways.items():
            inbound = gw_data.get('inbound', []) + gw_data.get('inbound_extra', [])
            outbound = gw_data.get('outbound', []) + gw_data.get('outbound_extra', [])

            # Count unique organizations/departments connected
            connected_orgs = set()
            connected_depts = set()

            for mqmgr in inbound + outbound:
                if mqmgr in self.all_mqmanagers:
                    connected_orgs.add(self.all_mqmanagers[mqmgr].get('Organization', ''))
                    connected_depts.add(self.all_mqmanagers[mqmgr].get('Department', ''))

            self.analytics['gateway_traffic'][gw_name] = {
                'scope': gw_data.get('GatewayScope', ''),
                'organization': gw_data.get('Organization', ''),
                'department': gw_data.get('Department', ''),
                'inbound_connections': len(inbound),
                'outbound_connections': len(outbound),
                'total_connections': len(inbound) + len(outbound),
                'connected_organizations': len(connected_orgs),
                'connected_departments': len(connected_depts),
                'queue_local': gw_data.get('qlocal_count', 0),
                'queue_remote': gw_data.get('qremote_count', 0),
                'queue_alias': gw_data.get('qalias_count', 0)
            }

    def _analyze_org_connectivity(self):
        """Analyze which organizations communicate through gateways."""
        org_pairs = defaultdict(lambda: {'gateways': set(), 'connection_count': 0})

        for gw_name, gw_data in self.gateways.items():
            gw_org = gw_data.get('Organization', '')
            connections = (gw_data.get('inbound', []) + gw_data.get('outbound', []) +
                          gw_data.get('inbound_extra', []) + gw_data.get('outbound_extra', []))

            for mqmgr in connections:
                if mqmgr in self.all_mqmanagers:
                    remote_org = self.all_mqmanagers[mqmgr].get('Organization', '')
                    if remote_org != gw_org:
                        pair_key = tuple(sorted([gw_org, remote_org]))
                        org_pairs[pair_key]['gateways'].add(gw_name)
                        org_pairs[pair_key]['connection_count'] += 1

        # Convert to serializable format
        self.analytics['org_connectivity'] = {
            f"{org1} <-> {org2}": {
                'gateways': list(data['gateways']),
                'connection_count': data['connection_count']
            }
            for (org1, org2), data in org_pairs.items()
        }

    def _analyze_department_connectivity(self):
        """Analyze which departments communicate through internal gateways."""
        dept_pairs = defaultdict(lambda: {'gateways': set(), 'connection_count': 0})

        internal_gateways = {
            name: data for name, data in self.gateways.items()
            if data.get('GatewayScope') == 'Internal'
        }

        for gw_name, gw_data in internal_gateways.items():
            gw_dept = gw_data.get('Department', '')
            connections = (gw_data.get('inbound', []) + gw_data.get('outbound', []) +
                          gw_data.get('inbound_extra', []) + gw_data.get('outbound_extra', []))

            for mqmgr in connections:
                if mqmgr in self.all_mqmanagers:
                    remote_dept = self.all_mqmanagers[mqmgr].get('Department', '')
                    if remote_dept != gw_dept:
                        pair_key = tuple(sorted([gw_dept, remote_dept]))
                        dept_pairs[pair_key]['gateways'].add(gw_name)
                        dept_pairs[pair_key]['connection_count'] += 1

        # Convert to serializable format
        self.analytics['department_connectivity'] = {
            f"{dept1} <-> {dept2}": {
                'gateways': list(data['gateways']),
                'connection_count': data['connection_count']
            }
            for (dept1, dept2), data in dept_pairs.items()
        }

    def _analyze_dependencies(self):
        """Identify applications/MQ managers dependent on each gateway."""
        for gw_name, gw_data in self.gateways.items():
            dependencies = set()
            connections = (gw_data.get('inbound', []) + gw_data.get('outbound', []) +
                          gw_data.get('inbound_extra', []) + gw_data.get('outbound_extra', []))

            for mqmgr in connections:
                if mqmgr in self.all_mqmanagers:
                    app = self.all_mqmanagers[mqmgr].get('Application', '')
                    if app and not app.startswith('Gateway ('):
                        dependencies.add(app)

            self.analytics['gateway_dependencies'][gw_name] = {
                'dependent_mqmanagers': len(connections),
                'dependent_applications': list(dependencies),
                'application_count': len(dependencies)
            }

    def _analyze_load_distribution(self):
        """Analyze load distribution across gateways."""
        internal_loads = []
        external_loads = []

        for gw_name, gw_data in self.gateways.items():
            total_connections = (len(gw_data.get('inbound', [])) + len(gw_data.get('outbound', [])) +
                               len(gw_data.get('inbound_extra', [])) + len(gw_data.get('outbound_extra', [])))
            total_queues = (gw_data.get('qlocal_count', 0) + gw_data.get('qremote_count', 0) +
                          gw_data.get('qalias_count', 0))

            load_data = {
                'gateway': gw_name,
                'connections': total_connections,
                'queues': total_queues,
                'load_score': total_connections * 2 + total_queues  # Weighted score
            }

            if gw_data.get('GatewayScope') == 'Internal':
                internal_loads.append(load_data)
            else:
                external_loads.append(load_data)

        # Sort by load score
        internal_loads.sort(key=lambda x: x['load_score'], reverse=True)
        external_loads.sort(key=lambda x: x['load_score'], reverse=True)

        self.analytics['load_distribution'] = {
            'internal_gateways': internal_loads,
            'external_gateways': external_loads
        }

    def _analyze_redundancy(self):
        """Analyze gateway redundancy for critical org/dept connections."""
        # Identify single points of failure
        spof = []

        for route, data in self.analytics['org_connectivity'].items():
            if len(data['gateways']) == 1:
                spof.append({
                    'route': route,
                    'gateway': data['gateways'][0],
                    'connection_count': data['connection_count'],
                    'type': 'Organization'
                })

        for route, data in self.analytics['department_connectivity'].items():
            if len(data['gateways']) == 1:
                spof.append({
                    'route': route,
                    'gateway': data['gateways'][0],
                    'connection_count': data['connection_count'],
                    'type': 'Department'
                })

        self.analytics['redundancy_analysis'] = {
            'single_points_of_failure': spof,
            'spof_count': len(spof),
            'routes_with_redundancy': (
                len([d for d in self.analytics['org_connectivity'].values() if len(d['gateways']) > 1]) +
                len([d for d in self.analytics['department_connectivity'].values() if len(d['gateways']) > 1])
            )
        }


def generate_gateway_report_html(analytics: Dict, output_file: Path):
    """Generate an HTML report for gateway analytics with rich UI."""
    from utils.report_styles import get_report_css, get_report_js

    summary = analytics['summary']
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Find max load score for CSS bar chart scaling
    all_loads = (analytics['load_distribution']['internal_gateways'] +
                 analytics['load_distribution']['external_gateways'])
    max_load = max((ld['load_score'] for ld in all_loads), default=1) or 1

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gateway Analytics Report</title>
    <style>{get_report_css('#9b59b6')}</style>
</head>
<body>
    <div class="hero">
        <h1>Gateway Analytics Report</h1>
        <p>Traffic patterns, dependencies, and redundancy analysis</p>
        <div class="meta">
            <span>Generated: {generated_at}</span>
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
            <div class="summary-card accent">
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

    for gw_name, traffic in sorted(analytics['gateway_traffic'].items(), key=lambda x: x[1]['total_connections'], reverse=True):
        scope_class = traffic['scope'].lower() if traffic['scope'] else 'internal'
        html += f"""
                    <tr>
                        <td><strong>{gw_name}</strong></td>
                        <td><span class="badge badge-{scope_class}">{traffic['scope']}</span></td>
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
    redundancy = analytics['redundancy_analysis']
    if redundancy['spof_count'] > 0:
        html += f"""
        <div class="alert alert-danger">
            <h3>Single Points of Failure Detected</h3>
            <p>Found <strong>{redundancy['spof_count']}</strong> critical routes with no gateway redundancy.</p>
        </div>
        <div class="section">
            <h2>Single Points of Failure</h2>
            <table>
                <thead>
                    <tr>
                        <th>Route</th>
                        <th>Type</th>
                        <th>Gateway</th>
                        <th>Connections</th>
                    </tr>
                </thead>
                <tbody>
"""
        for spof in redundancy['single_points_of_failure']:
            html += f"""
                    <tr>
                        <td>{spof['route']}</td>
                        <td>{spof['type']}</td>
                        <td><strong>{spof['gateway']}</strong></td>
                        <td>{spof['connection_count']}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
        </div>
"""
    else:
        html += """
        <div class="alert alert-success">
            <h3>Gateway Redundancy OK</h3>
            <p>All critical routes have redundant gateways configured.</p>
        </div>
"""

    # Load Distribution with CSS bar charts
    def _load_table_rows(loads):
        rows = ""
        for ld in loads:
            bar_pct = int(ld['load_score'] / max_load * 100)
            rows += f"""
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
        return rows

    html += """
        <div class="section">
            <h2>Load Distribution</h2>
"""
    if analytics['load_distribution']['internal_gateways']:
        html += """
            <details open>
            <summary>Internal Gateways</summary>
            <div class="detail-body">
            <table>
                <thead>
                    <tr>
                        <th>Gateway</th>
                        <th>Connections</th>
                        <th>Queues</th>
                        <th>Load Score</th>
                    </tr>
                </thead>
                <tbody>
"""
        html += _load_table_rows(analytics['load_distribution']['internal_gateways'])
        html += """
                </tbody>
            </table>
            </div>
            </details>
"""

    if analytics['load_distribution']['external_gateways']:
        html += """
            <details open>
            <summary>External Gateways</summary>
            <div class="detail-body">
            <table>
                <thead>
                    <tr>
                        <th>Gateway</th>
                        <th>Connections</th>
                        <th>Queues</th>
                        <th>Load Score</th>
                    </tr>
                </thead>
                <tbody>
"""
        html += _load_table_rows(analytics['load_distribution']['external_gateways'])
        html += """
                </tbody>
            </table>
            </div>
            </details>
"""
    html += """
        </div>
"""

    # Organization Connectivity Matrix
    html += """
        <div class="section">
            <h2>Organization Connectivity Matrix</h2>
            <table>
                <thead>
                    <tr>
                        <th>Organization Route</th>
                        <th>Gateways</th>
                        <th>Connections</th>
                        <th>Redundancy</th>
                    </tr>
                </thead>
                <tbody>
"""
    for route, data in sorted(analytics['org_connectivity'].items(), key=lambda x: x[1]['connection_count'], reverse=True):
        redundancy_badge = '<span class="badge badge-ok">Yes</span>' if len(data['gateways']) > 1 else '<span class="badge badge-warning">No</span>'
        html += f"""
                    <tr>
                        <td>{route}</td>
                        <td>{', '.join(data['gateways'])}</td>
                        <td>{data['connection_count']}</td>
                        <td>{redundancy_badge}</td>
                    </tr>
"""
    html += """
                </tbody>
            </table>
        </div>
"""

    # Gateway Dependencies (collapsible per gateway)
    if analytics['gateway_dependencies']:
        html += """
        <div class="section">
            <h2>Gateway Dependencies</h2>
"""
        for gw_name, deps in sorted(analytics['gateway_dependencies'].items()):
            apps_list = ', '.join(deps['dependent_applications']) if deps['dependent_applications'] else 'None'
            html += f"""
            <details>
                <summary>{gw_name} &mdash; {deps['application_count']} apps, {deps['dependent_mqmanagers']} MQ managers</summary>
                <div class="detail-body">
                    <p><strong>Dependent Applications:</strong> {apps_list}</p>
                </div>
            </details>
"""
        html += """
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

    logger.info(f"✓ Gateway analytics report generated: {output_file}")