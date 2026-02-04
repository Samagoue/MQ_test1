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
        gateways = {}

        for org_name, org_data in self.data.items():
            if not isinstance(org_data, dict) or '_departments' not in org_data:
                continue

            for dept_name, dept_data in org_data['_departments'].items():
                for biz_ownr, applications in dept_data.items():
                    for app_name, mqmgr_dict in applications.items():
                        for mqmgr_name, mqmgr_data in mqmgr_dict.items():
                            if mqmgr_data.get('IsGateway', False):
                                gateways[mqmgr_name] = mqmgr_data

        return gateways

    def _extract_all_mqmanagers(self) -> Dict[str, Dict]:
        """Extract all MQ managers from the data."""
        mqmanagers = {}

        for org_name, org_data in self.data.items():
            if not isinstance(org_data, dict) or '_departments' not in org_data:
                continue

            for dept_name, dept_data in org_data['_departments'].items():
                for biz_ownr, applications in dept_data.items():
                    for app_name, mqmgr_dict in applications.items():
                        for mqmgr_name, mqmgr_data in mqmgr_dict.items():
                            mqmanagers[mqmgr_name] = mqmgr_data

        return mqmanagers

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
    """Generate an HTML report for gateway analytics."""
    summary = analytics['summary']

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gateway Analytics Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #9b59b6;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            border-left: 4px solid #9b59b6;
            padding-left: 10px;
            margin-top: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #9b59b6 0%, #e91e63 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card.internal {{ background: linear-gradient(135deg, #ff9800 0%, #ff5722 100%); }}
        .summary-card.external {{ background: linear-gradient(135deg, #00bcd4 0%, #009688 100%); }}
        .summary-card h3 {{ margin: 0 0 10px 0; font-size: 14px; }}
        .summary-card .count {{ font-size: 36px; font-weight: bold; }}
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
            background-color: #9b59b6;
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
        .badge-internal {{ background-color: #ff9800; color: white; }}
        .badge-external {{ background-color: #00bcd4; color: white; }}
        .badge-warning {{ background-color: #e74c3c; color: white; }}
        .badge-ok {{ background-color: #27ae60; color: white; }}
        .chart-bar {{
            background-color: #9b59b6;
            color: white;
            padding: 5px 10px;
            margin: 2px 0;
            border-radius: 3px;
        }}
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
    </style>
</head>
<body>
    <div class="container">
        <h1>🔀 Gateway Analytics Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="summary">
            <div class="summary-card">
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
            <div class="summary-card">
                <h3>Total Connections</h3>
                <div class="count">{summary['total_gateway_connections']}</div>
            </div>
        </div>

        <h2>📊 Gateway Traffic Overview</h2>
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
        scope_badge = f'<span class="badge badge-{traffic["scope"].lower()}">{traffic["scope"]}</span>'
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
"""

    # Redundancy Analysis
    redundancy = analytics['redundancy_analysis']
    if redundancy['spof_count'] > 0:
        html += f"""
        <div class="alert alert-danger">
            <h2>⚠ Single Points of Failure Detected</h2>
            <p>Found <strong>{redundancy['spof_count']}</strong> critical routes with no gateway redundancy:</p>
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
        <div class="alert">
            <h2>✅ Gateway Redundancy</h2>
            <p>All critical routes have redundant gateways configured.</p>
        </div>
"""

    # Load Distribution
    html += """
        <h2>⚖️ Load Distribution</h2>
        <h3>Internal Gateways</h3>
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
    for load in analytics['load_distribution']['internal_gateways']:
        html += f"""
                <tr>
                    <td>{load['gateway']}</td>
                    <td>{load['connections']}</td>
                    <td>{load['queues']}</td>
                    <td><strong>{load['load_score']}</strong></td>
                </tr>
"""
    html += """
            </tbody>
        </table>

        <h3>External Gateways</h3>
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
    for load in analytics['load_distribution']['external_gateways']:
        html += f"""
                <tr>
                    <td>{load['gateway']}</td>
                    <td>{load['connections']}</td>
                    <td>{load['queues']}</td>
                    <td><strong>{load['load_score']}</strong></td>
                </tr>
"""
    html += """
            </tbody>
        </table>

        <h2>🔗 Organization Connectivity Matrix</h2>
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
        redundancy_badge = f'<span class="badge badge-ok">Yes</span>' if len(data['gateways']) > 1 else '<span class="badge badge-warning">No</span>'
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
</body>
</html>
"""

    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ Gateway analytics report generated: {output_file}")
