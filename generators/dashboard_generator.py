"""
Interactive HTML Dashboard Generator

Generates a single-page HTML dashboard with:
- Summary KPIs and statistics
- Interactive search and filtering
- Drill-down navigation (Org → Dept → App → MQ Manager)
- Embedded SVG topology
- Gateway overview
- Connection analysis
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict


class DashboardGenerator:
    """Generate interactive HTML dashboard from enriched MQ CMDB data."""

    def __init__(self, enriched_data: Dict):
        """
        Initialize dashboard generator.

        Args:
            enriched_data: Enriched MQ CMDB data from hierarchy mashup
        """
        self.data = enriched_data
        self.stats = self._calculate_stats()

    def _calculate_stats(self) -> Dict:
        """Calculate summary statistics from the data."""
        stats = {
            'total_orgs': 0,
            'total_depts': 0,
            'total_biz_owners': 0,
            'total_apps': 0,
            'total_mqmgrs': 0,
            'total_qlocal': 0,
            'total_qremote': 0,
            'total_qalias': 0,
            'total_connections': 0,
            'total_gateways': 0,
            'internal_gateways': 0,
            'external_gateways': 0,
            'internal_orgs': 0,
            'external_orgs': 0,
            'mqmanagers': [],
            'applications': set(),
            'organizations': [],
            'connections': []
        }

        for org_name, org_data in self.data.items():
            if not isinstance(org_data, dict) or '_departments' not in org_data:
                continue

            stats['total_orgs'] += 1
            org_type = org_data.get('_org_type', 'Internal')
            if org_type == 'External':
                stats['external_orgs'] += 1
            else:
                stats['internal_orgs'] += 1

            stats['organizations'].append({
                'name': org_name,
                'type': org_type,
                'departments': len(org_data.get('_departments', {}))
            })

            for dept_name, dept_data in org_data.get('_departments', {}).items():
                stats['total_depts'] += 1

                for biz_ownr, applications in dept_data.items():
                    stats['total_biz_owners'] += 1

                    for app_name, mqmanagers in applications.items():
                        stats['total_apps'] += 1
                        stats['applications'].add(app_name)

                        for mqmgr_name, mq_data in mqmanagers.items():
                            stats['total_mqmgrs'] += 1
                            stats['total_qlocal'] += mq_data.get('qlocal_count', 0)
                            stats['total_qremote'] += mq_data.get('qremote_count', 0)
                            stats['total_qalias'] += mq_data.get('qalias_count', 0)

                            outbound = mq_data.get('outbound', [])
                            inbound = mq_data.get('inbound', [])
                            stats['total_connections'] += len(outbound)

                            for target in outbound:
                                stats['connections'].append({
                                    'source': mqmgr_name,
                                    'target': target,
                                    'source_org': org_name,
                                    'source_app': app_name
                                })

                            is_gateway = mq_data.get('IsGateway', False)
                            if is_gateway:
                                stats['total_gateways'] += 1
                                scope = mq_data.get('GatewayScope', 'Internal')
                                if scope == 'External':
                                    stats['external_gateways'] += 1
                                else:
                                    stats['internal_gateways'] += 1

                            stats['mqmanagers'].append({
                                'name': mqmgr_name,
                                'organization': org_name,
                                'department': dept_name,
                                'biz_owner': biz_ownr,
                                'application': app_name,
                                'qlocal': mq_data.get('qlocal_count', 0),
                                'qremote': mq_data.get('qremote_count', 0),
                                'qalias': mq_data.get('qalias_count', 0),
                                'inbound_count': len(inbound) + len(mq_data.get('inbound_extra', [])),
                                'outbound_count': len(outbound) + len(mq_data.get('outbound_extra', [])),
                                'is_gateway': is_gateway,
                                'gateway_scope': mq_data.get('GatewayScope', ''),
                                'org_type': org_type
                            })

        stats['applications'] = sorted(list(stats['applications']))
        return stats

    def generate(self, output_file: Path) -> bool:
        """
        Generate the HTML dashboard.

        Args:
            output_file: Path to save the HTML file

        Returns:
            True if successful
        """
        html = self._generate_html()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html, encoding='utf-8')
        print(f"✓ Dashboard generated: {output_file}")
        return True

    def _generate_html(self) -> str:
        """Generate the complete HTML dashboard."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Convert data to JSON for JavaScript
        mqmanagers_json = json.dumps(self.stats['mqmanagers'], indent=2)
        connections_json = json.dumps(self.stats['connections'], indent=2)
        orgs_json = json.dumps(self.stats['organizations'], indent=2)

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MQ CMDB Dashboard</title>
    <style>
        :root {{
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --purple: #8b5cf6;
            --teal: #14b8a6;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-300: #d1d5db;
            --gray-500: #6b7280;
            --gray-700: #374151;
            --gray-900: #111827;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--gray-100);
            color: var(--gray-900);
            line-height: 1.5;
        }}

        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 1.5rem 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}

        .header h1 {{
            font-size: 1.75rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
        }}

        .header .subtitle {{
            opacity: 0.9;
            font-size: 0.875rem;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 1.5rem;
        }}

        /* KPI Cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .kpi-card {{
            background: white;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border-left: 4px solid var(--primary);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }}

        .kpi-card.gateway {{
            border-left-color: var(--warning);
        }}

        .kpi-card.external {{
            border-left-color: var(--purple);
        }}

        .kpi-card.connection {{
            border-left-color: var(--teal);
        }}

        .kpi-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--gray-900);
        }}

        .kpi-label {{
            font-size: 0.875rem;
            color: var(--gray-500);
            margin-top: 0.25rem;
        }}

        .kpi-detail {{
            font-size: 0.75rem;
            color: var(--gray-500);
            margin-top: 0.5rem;
            padding-top: 0.5rem;
            border-top: 1px solid var(--gray-200);
        }}

        /* Section Cards */
        .section {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 1.5rem;
            overflow: hidden;
        }}

        .section-header {{
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--gray-200);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--gray-50);
        }}

        .section-title {{
            font-size: 1.125rem;
            font-weight: 600;
            color: var(--gray-900);
        }}

        .section-body {{
            padding: 1.5rem;
        }}

        /* Search and Filter */
        .search-container {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin-bottom: 1rem;
        }}

        .search-input {{
            flex: 1;
            min-width: 250px;
            padding: 0.75rem 1rem;
            border: 1px solid var(--gray-300);
            border-radius: 8px;
            font-size: 0.875rem;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}

        .search-input:focus {{
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }}

        .filter-select {{
            padding: 0.75rem 1rem;
            border: 1px solid var(--gray-300);
            border-radius: 8px;
            font-size: 0.875rem;
            background: white;
            min-width: 150px;
            cursor: pointer;
        }}

        /* Table */
        .table-container {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}

        th {{
            background: var(--gray-50);
            padding: 0.75rem 1rem;
            text-align: left;
            font-weight: 600;
            color: var(--gray-700);
            border-bottom: 2px solid var(--gray-200);
            white-space: nowrap;
            cursor: pointer;
            user-select: none;
        }}

        th:hover {{
            background: var(--gray-100);
        }}

        th .sort-icon {{
            margin-left: 0.5rem;
            opacity: 0.5;
        }}

        td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--gray-200);
            vertical-align: middle;
        }}

        tr:hover {{
            background: var(--gray-50);
        }}

        /* Badges */
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
        }}

        .badge-internal {{
            background: #dbeafe;
            color: #1e40af;
        }}

        .badge-external {{
            background: #ede9fe;
            color: #5b21b6;
        }}

        .badge-gateway {{
            background: #fef3c7;
            color: #92400e;
        }}

        .badge-gateway-ext {{
            background: #ccfbf1;
            color: #0f766e;
        }}

        /* Connection indicators */
        .connection-indicator {{
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
        }}

        .in-arrow {{
            color: var(--success);
        }}

        .out-arrow {{
            color: var(--primary);
        }}

        /* Tabs */
        .tabs {{
            display: flex;
            border-bottom: 1px solid var(--gray-200);
            margin-bottom: 1rem;
        }}

        .tab {{
            padding: 0.75rem 1.5rem;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            color: var(--gray-500);
            font-weight: 500;
            transition: all 0.2s;
        }}

        .tab:hover {{
            color: var(--gray-700);
        }}

        .tab.active {{
            color: var(--primary);
            border-bottom-color: var(--primary);
        }}

        .tab-content {{
            display: none;
        }}

        .tab-content.active {{
            display: block;
        }}

        /* Hierarchy Tree */
        .hierarchy {{
            font-size: 0.875rem;
        }}

        .hierarchy-item {{
            padding: 0.5rem 0;
        }}

        .hierarchy-toggle {{
            cursor: pointer;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .hierarchy-toggle:hover {{
            color: var(--primary);
        }}

        .hierarchy-children {{
            margin-left: 1.5rem;
            border-left: 1px solid var(--gray-200);
            padding-left: 1rem;
            display: none;
        }}

        .hierarchy-children.expanded {{
            display: block;
        }}

        .hierarchy-icon {{
            width: 1.25rem;
            text-align: center;
        }}

        .hierarchy-count {{
            background: var(--gray-200);
            color: var(--gray-700);
            padding: 0.125rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            margin-left: auto;
        }}

        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
        }}

        .stat-item {{
            text-align: center;
            padding: 1rem;
            background: var(--gray-50);
            border-radius: 8px;
        }}

        .stat-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--gray-900);
        }}

        .stat-label {{
            font-size: 0.75rem;
            color: var(--gray-500);
            margin-top: 0.25rem;
        }}

        /* Grid layout */
        .grid-2 {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1.5rem;
        }}

        @media (max-width: 1024px) {{
            .grid-2 {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 1.5rem;
            color: var(--gray-500);
            font-size: 0.875rem;
        }}

        /* Clickable rows */
        .clickable {{
            cursor: pointer;
        }}

        .clickable:hover {{
            background: #f0f7ff !important;
        }}

        /* Progress bar */
        .progress-bar {{
            height: 8px;
            background: var(--gray-200);
            border-radius: 4px;
            overflow: hidden;
        }}

        .progress-fill {{
            height: 100%;
            background: var(--primary);
            border-radius: 4px;
        }}

        /* No results */
        .no-results {{
            text-align: center;
            padding: 3rem;
            color: var(--gray-500);
        }}

        /* Connection list */
        .connection-list {{
            max-height: 400px;
            overflow-y: auto;
        }}

        .connection-item {{
            display: flex;
            align-items: center;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--gray-100);
        }}

        .connection-source {{
            flex: 1;
            font-weight: 500;
        }}

        .connection-arrow {{
            padding: 0 1rem;
            color: var(--gray-400);
        }}

        .connection-target {{
            flex: 1;
            text-align: right;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>MQ CMDB Dashboard</h1>
        <div class="subtitle">Generated: {timestamp}</div>
    </div>

    <div class="container">
        <!-- KPI Cards -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-value">{self.stats['total_mqmgrs']}</div>
                <div class="kpi-label">MQ Managers</div>
                <div class="kpi-detail">{self.stats['total_apps']} Applications</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{self.stats['total_orgs']}</div>
                <div class="kpi-label">Organizations</div>
                <div class="kpi-detail">{self.stats['internal_orgs']} Internal / {self.stats['external_orgs']} External</div>
            </div>
            <div class="kpi-card connection">
                <div class="kpi-value">{self.stats['total_connections']}</div>
                <div class="kpi-label">Connections</div>
                <div class="kpi-detail">{self.stats['total_depts']} Departments</div>
            </div>
            <div class="kpi-card gateway">
                <div class="kpi-value">{self.stats['total_gateways']}</div>
                <div class="kpi-label">Gateways</div>
                <div class="kpi-detail">{self.stats['internal_gateways']} Internal / {self.stats['external_gateways']} External</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{self.stats['total_qlocal']}</div>
                <div class="kpi-label">QLocal Queues</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{self.stats['total_qremote']}</div>
                <div class="kpi-label">QRemote Queues</div>
            </div>
            <div class="kpi-card external">
                <div class="kpi-value">{self.stats['total_qalias']}</div>
                <div class="kpi-label">QAlias Queues</div>
            </div>
        </div>

        <!-- Main Content Tabs -->
        <div class="section">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('mqmanagers')">MQ Managers</div>
                <div class="tab" onclick="switchTab('hierarchy')">Hierarchy</div>
                <div class="tab" onclick="switchTab('connections')">Connections</div>
                <div class="tab" onclick="switchTab('gateways')">Gateways</div>
            </div>

            <!-- MQ Managers Tab -->
            <div id="mqmanagers" class="tab-content active">
                <div class="section-body">
                    <div class="search-container">
                        <input type="text" class="search-input" id="searchInput" placeholder="Search MQ Managers, Applications, Organizations..." oninput="filterTable()">
                        <select class="filter-select" id="orgFilter" onchange="filterTable()">
                            <option value="">All Organizations</option>
                        </select>
                        <select class="filter-select" id="typeFilter" onchange="filterTable()">
                            <option value="">All Types</option>
                            <option value="internal">Internal Only</option>
                            <option value="external">External Only</option>
                            <option value="gateway">Gateways Only</option>
                        </select>
                    </div>
                    <div class="table-container">
                        <table id="mqTable">
                            <thead>
                                <tr>
                                    <th onclick="sortTable(0)">MQ Manager <span class="sort-icon">↕</span></th>
                                    <th onclick="sortTable(1)">Application <span class="sort-icon">↕</span></th>
                                    <th onclick="sortTable(2)">Organization <span class="sort-icon">↕</span></th>
                                    <th onclick="sortTable(3)">Department <span class="sort-icon">↕</span></th>
                                    <th onclick="sortTable(4)">Type <span class="sort-icon">↕</span></th>
                                    <th onclick="sortTable(5)">Queues <span class="sort-icon">↕</span></th>
                                    <th onclick="sortTable(6)">Connections <span class="sort-icon">↕</span></th>
                                </tr>
                            </thead>
                            <tbody id="mqTableBody">
                            </tbody>
                        </table>
                    </div>
                    <div id="noResults" class="no-results" style="display: none;">
                        No MQ Managers found matching your criteria
                    </div>
                </div>
            </div>

            <!-- Hierarchy Tab -->
            <div id="hierarchy" class="tab-content">
                <div class="section-body">
                    <div class="hierarchy" id="hierarchyTree">
                    </div>
                </div>
            </div>

            <!-- Connections Tab -->
            <div id="connections" class="tab-content">
                <div class="section-body">
                    <div class="grid-2">
                        <div>
                            <h3 style="margin-bottom: 1rem; color: var(--gray-700);">Top Connected MQ Managers</h3>
                            <div id="topConnected"></div>
                        </div>
                        <div>
                            <h3 style="margin-bottom: 1rem; color: var(--gray-700);">Recent Connections</h3>
                            <div class="connection-list" id="connectionList"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Gateways Tab -->
            <div id="gateways" class="tab-content">
                <div class="section-body">
                    <div class="grid-2">
                        <div>
                            <h3 style="margin-bottom: 1rem; color: var(--gray-700);">Internal Gateways</h3>
                            <div id="internalGateways"></div>
                        </div>
                        <div>
                            <h3 style="margin-bottom: 1rem; color: var(--gray-700);">External Gateways</h3>
                            <div id="externalGateways"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Quick Stats -->
        <div class="grid-2">
            <div class="section">
                <div class="section-header">
                    <span class="section-title">Queue Distribution</span>
                </div>
                <div class="section-body">
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-value">{self.stats['total_qlocal']}</div>
                            <div class="stat-label">QLocal</div>
                            <div class="progress-bar" style="margin-top: 0.5rem;">
                                <div class="progress-fill" style="width: {self._queue_percent('qlocal')}%; background: var(--success);"></div>
                            </div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{self.stats['total_qremote']}</div>
                            <div class="stat-label">QRemote</div>
                            <div class="progress-bar" style="margin-top: 0.5rem;">
                                <div class="progress-fill" style="width: {self._queue_percent('qremote')}%; background: var(--primary);"></div>
                            </div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{self.stats['total_qalias']}</div>
                            <div class="stat-label">QAlias</div>
                            <div class="progress-bar" style="margin-top: 0.5rem;">
                                <div class="progress-fill" style="width: {self._queue_percent('qalias')}%; background: var(--purple);"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-header">
                    <span class="section-title">Organization Breakdown</span>
                </div>
                <div class="section-body">
                    <div id="orgBreakdown"></div>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        MQ CMDB Automation System | Dashboard v1.0
    </div>

    <script>
        // Data
        const mqmanagers = {mqmanagers_json};
        const connections = {connections_json};
        const organizations = {orgs_json};

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {{
            populateTable();
            populateFilters();
            buildHierarchy();
            populateConnections();
            populateGateways();
            populateOrgBreakdown();
        }});

        // Tab switching
        function switchTab(tabId) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelector(`[onclick="switchTab('${{tabId}}')"]`).classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }}

        // Populate table
        function populateTable() {{
            const tbody = document.getElementById('mqTableBody');
            tbody.innerHTML = '';

            mqmanagers.forEach(mq => {{
                const row = document.createElement('tr');
                row.className = 'clickable';

                let typeBadge = '';
                if (mq.is_gateway) {{
                    typeBadge = mq.gateway_scope === 'External'
                        ? '<span class="badge badge-gateway-ext">Gateway (Ext)</span>'
                        : '<span class="badge badge-gateway">Gateway (Int)</span>';
                }} else {{
                    typeBadge = mq.org_type === 'External'
                        ? '<span class="badge badge-external">External</span>'
                        : '<span class="badge badge-internal">Internal</span>';
                }}

                row.innerHTML = `
                    <td><strong>${{mq.name}}</strong></td>
                    <td>${{mq.application}}</td>
                    <td>${{mq.organization}}</td>
                    <td>${{mq.department}}</td>
                    <td>${{typeBadge}}</td>
                    <td>
                        <span style="color: var(--success)">${{mq.qlocal}}</span> /
                        <span style="color: var(--primary)">${{mq.qremote}}</span> /
                        <span style="color: var(--purple)">${{mq.qalias}}</span>
                    </td>
                    <td>
                        <span class="connection-indicator">
                            <span class="in-arrow">↓${{mq.inbound_count}}</span>
                            <span class="out-arrow">↑${{mq.outbound_count}}</span>
                        </span>
                    </td>
                `;
                tbody.appendChild(row);
            }});
        }}

        // Populate filters
        function populateFilters() {{
            const orgFilter = document.getElementById('orgFilter');
            const uniqueOrgs = [...new Set(mqmanagers.map(m => m.organization))].sort();
            uniqueOrgs.forEach(org => {{
                const option = document.createElement('option');
                option.value = org;
                option.textContent = org;
                orgFilter.appendChild(option);
            }});
        }}

        // Filter table
        function filterTable() {{
            const search = document.getElementById('searchInput').value.toLowerCase();
            const org = document.getElementById('orgFilter').value;
            const type = document.getElementById('typeFilter').value;

            const rows = document.querySelectorAll('#mqTableBody tr');
            let visibleCount = 0;

            rows.forEach((row, index) => {{
                const mq = mqmanagers[index];
                let show = true;

                // Search filter
                if (search) {{
                    const searchText = `${{mq.name}} ${{mq.application}} ${{mq.organization}} ${{mq.department}}`.toLowerCase();
                    if (!searchText.includes(search)) show = false;
                }}

                // Org filter
                if (org && mq.organization !== org) show = false;

                // Type filter
                if (type === 'internal' && mq.org_type !== 'Internal') show = false;
                if (type === 'external' && mq.org_type !== 'External') show = false;
                if (type === 'gateway' && !mq.is_gateway) show = false;

                row.style.display = show ? '' : 'none';
                if (show) visibleCount++;
            }});

            document.getElementById('noResults').style.display = visibleCount === 0 ? 'block' : 'none';
        }}

        // Sort table
        let sortDirection = {{}};
        function sortTable(columnIndex) {{
            const tbody = document.getElementById('mqTableBody');
            const rows = Array.from(tbody.querySelectorAll('tr'));

            sortDirection[columnIndex] = !sortDirection[columnIndex];
            const dir = sortDirection[columnIndex] ? 1 : -1;

            rows.sort((a, b) => {{
                const aVal = a.cells[columnIndex].textContent.trim();
                const bVal = b.cells[columnIndex].textContent.trim();
                return aVal.localeCompare(bVal) * dir;
            }});

            rows.forEach(row => tbody.appendChild(row));
        }}

        // Build hierarchy tree
        function buildHierarchy() {{
            const tree = document.getElementById('hierarchyTree');
            const hierarchy = {{}};

            mqmanagers.forEach(mq => {{
                if (!hierarchy[mq.organization]) {{
                    hierarchy[mq.organization] = {{ type: mq.org_type, depts: {{}} }};
                }}
                if (!hierarchy[mq.organization].depts[mq.department]) {{
                    hierarchy[mq.organization].depts[mq.department] = {{ apps: {{}} }};
                }}
                if (!hierarchy[mq.organization].depts[mq.department].apps[mq.application]) {{
                    hierarchy[mq.organization].depts[mq.department].apps[mq.application] = [];
                }}
                hierarchy[mq.organization].depts[mq.department].apps[mq.application].push(mq);
            }});

            let html = '';
            Object.entries(hierarchy).forEach(([orgName, orgData]) => {{
                const orgId = orgName.replace(/\\s+/g, '_');
                const deptCount = Object.keys(orgData.depts).length;
                const typeClass = orgData.type === 'External' ? 'badge-external' : 'badge-internal';

                html += `
                    <div class="hierarchy-item">
                        <div class="hierarchy-toggle" onclick="toggleHierarchy('${{orgId}}')">
                            <span class="hierarchy-icon">▶</span>
                            <strong>${{orgName}}</strong>
                            <span class="badge ${{typeClass}}">${{orgData.type}}</span>
                            <span class="hierarchy-count">${{deptCount}} depts</span>
                        </div>
                        <div class="hierarchy-children" id="${{orgId}}">
                `;

                Object.entries(orgData.depts).forEach(([deptName, deptData]) => {{
                    const deptId = `${{orgId}}_${{deptName.replace(/\\s+/g, '_')}}`;
                    const appCount = Object.keys(deptData.apps).length;

                    html += `
                        <div class="hierarchy-item">
                            <div class="hierarchy-toggle" onclick="toggleHierarchy('${{deptId}}')">
                                <span class="hierarchy-icon">▶</span>
                                ${{deptName}}
                                <span class="hierarchy-count">${{appCount}} apps</span>
                            </div>
                            <div class="hierarchy-children" id="${{deptId}}">
                    `;

                    Object.entries(deptData.apps).forEach(([appName, mqList]) => {{
                        const appId = `${{deptId}}_${{appName.replace(/\\s+/g, '_')}}`;

                        html += `
                            <div class="hierarchy-item">
                                <div class="hierarchy-toggle" onclick="toggleHierarchy('${{appId}}')">
                                    <span class="hierarchy-icon">▶</span>
                                    📦 ${{appName}}
                                    <span class="hierarchy-count">${{mqList.length}} MQ</span>
                                </div>
                                <div class="hierarchy-children" id="${{appId}}">
                        `;

                        mqList.forEach(mq => {{
                            const gwBadge = mq.is_gateway ? '<span class="badge badge-gateway">GW</span>' : '';
                            html += `
                                <div class="hierarchy-item">
                                    <span class="hierarchy-icon">🗄️</span>
                                    ${{mq.name}} ${{gwBadge}}
                                </div>
                            `;
                        }});

                        html += '</div></div>';
                    }});

                    html += '</div></div>';
                }});

                html += '</div></div>';
            }});

            tree.innerHTML = html;
        }}

        function toggleHierarchy(id) {{
            const el = document.getElementById(id);
            const icon = el.previousElementSibling.querySelector('.hierarchy-icon');
            if (el.classList.contains('expanded')) {{
                el.classList.remove('expanded');
                icon.textContent = '▶';
            }} else {{
                el.classList.add('expanded');
                icon.textContent = '▼';
            }}
        }}

        // Populate connections
        function populateConnections() {{
            // Top connected
            const connectionCounts = {{}};
            mqmanagers.forEach(mq => {{
                connectionCounts[mq.name] = mq.inbound_count + mq.outbound_count;
            }});

            const sorted = Object.entries(connectionCounts)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10);

            const topEl = document.getElementById('topConnected');
            let topHtml = '';
            sorted.forEach(([name, count]) => {{
                const pct = (count / Math.max(...Object.values(connectionCounts))) * 100;
                topHtml += `
                    <div style="margin-bottom: 0.75rem;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                            <span style="font-weight: 500;">${{name}}</span>
                            <span style="color: var(--gray-500);">${{count}}</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${{pct}}%;"></div>
                        </div>
                    </div>
                `;
            }});
            topEl.innerHTML = topHtml;

            // Connection list
            const connList = document.getElementById('connectionList');
            let connHtml = '';
            connections.slice(0, 50).forEach(conn => {{
                connHtml += `
                    <div class="connection-item">
                        <span class="connection-source">${{conn.source}}</span>
                        <span class="connection-arrow">→</span>
                        <span class="connection-target">${{conn.target}}</span>
                    </div>
                `;
            }});
            connList.innerHTML = connHtml || '<div class="no-results">No connections found</div>';
        }}

        // Populate gateways
        function populateGateways() {{
            const gateways = mqmanagers.filter(m => m.is_gateway);
            const internal = gateways.filter(g => g.gateway_scope !== 'External');
            const external = gateways.filter(g => g.gateway_scope === 'External');

            const renderGateway = (gw) => `
                <div style="padding: 1rem; background: var(--gray-50); border-radius: 8px; margin-bottom: 0.75rem;">
                    <div style="font-weight: 600; margin-bottom: 0.5rem;">🔗 ${{gw.name}}</div>
                    <div style="font-size: 0.875rem; color: var(--gray-500);">
                        ${{gw.organization}} / ${{gw.department}}
                    </div>
                    <div style="margin-top: 0.5rem; font-size: 0.875rem;">
                        <span class="in-arrow">↓${{gw.inbound_count}}</span>
                        <span class="out-arrow">↑${{gw.outbound_count}}</span>
                    </div>
                </div>
            `;

            document.getElementById('internalGateways').innerHTML =
                internal.length > 0 ? internal.map(renderGateway).join('') : '<div class="no-results">No internal gateways</div>';
            document.getElementById('externalGateways').innerHTML =
                external.length > 0 ? external.map(renderGateway).join('') : '<div class="no-results">No external gateways</div>';
        }}

        // Populate org breakdown
        function populateOrgBreakdown() {{
            const el = document.getElementById('orgBreakdown');
            let html = '';

            const orgCounts = {{}};
            mqmanagers.forEach(mq => {{
                orgCounts[mq.organization] = (orgCounts[mq.organization] || 0) + 1;
            }});

            const maxCount = Math.max(...Object.values(orgCounts));

            Object.entries(orgCounts)
                .sort((a, b) => b[1] - a[1])
                .forEach(([org, count]) => {{
                    const pct = (count / maxCount) * 100;
                    const orgData = organizations.find(o => o.name === org) || {{ type: 'Internal' }};
                    const color = orgData.type === 'External' ? 'var(--purple)' : 'var(--primary)';

                    html += `
                        <div style="margin-bottom: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                                <span style="font-weight: 500;">${{org}}</span>
                                <span style="color: var(--gray-500);">${{count}} MQ Managers</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${{pct}}%; background: ${{color}};"></div>
                            </div>
                        </div>
                    `;
                }});

            el.innerHTML = html;
        }}
    </script>
</body>
</html>'''

        return html

    def _queue_percent(self, queue_type: str) -> int:
        """Calculate percentage for queue type bar."""
        total = self.stats['total_qlocal'] + self.stats['total_qremote'] + self.stats['total_qalias']
        if total == 0:
            return 0
        if queue_type == 'qlocal':
            return int((self.stats['total_qlocal'] / total) * 100)
        elif queue_type == 'qremote':
            return int((self.stats['total_qremote'] / total) * 100)
        else:
            return int((self.stats['total_qalias'] / total) * 100)


def generate_dashboard(enriched_data: Dict, output_file: Path) -> bool:
    """
    Generate interactive HTML dashboard.

    Args:
        enriched_data: Enriched MQ CMDB data
        output_file: Path to save the HTML file

    Returns:
        True if successful
    """
    generator = DashboardGenerator(enriched_data)
    return generator.generate(output_file)
