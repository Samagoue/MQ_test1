"""
Enterprise Architecture Documentation Generator

Generates EA-driven documentation suitable for Confluence:
- Architecture overview and principles
- Component and integration views
- Capability model and dependency maps
- Risk analysis and recommendations
"""

from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime
from collections import defaultdict


class EADocumentationGenerator:
    """Generate Enterprise Architecture documentation for MQ CMDB topology."""

    def __init__(self, enriched_data: Dict):
        """
        Initialize EA documentation generator.

        Args:
            enriched_data: Enriched hierarchical MQ CMDB data
        """
        self.data = enriched_data
        self.stats = self._calculate_statistics()
        self.dependencies = self._analyze_dependencies()
        self.integration_patterns = self._identify_integration_patterns()

    def _calculate_statistics(self) -> Dict:
        """Calculate comprehensive statistics."""
        stats = {
            'organizations': {},
            'departments': set(),
            'mqmanagers': {},
            'gateways': [],
            'connections': {'internal': 0, 'cross_dept': 0, 'cross_org': 0},
            'queues': {'qlocal': 0, 'qremote': 0, 'qalias': 0, 'total': 0}
        }

        for org_name, org_data in self.data.items():
            if not isinstance(org_data, dict) or '_departments' not in org_data:
                continue

            org_type = org_data.get('_org_type', 'Internal')
            stats['organizations'][org_name] = {
                'type': org_type,
                'departments': set(),
                'mqmanagers': 0
            }

            for dept_name, dept_data in org_data['_departments'].items():
                stats['departments'].add(dept_name)
                stats['organizations'][org_name]['departments'].add(dept_name)

                for biz_ownr, applications in dept_data.items():
                    for app_name, mqmgr_dict in applications.items():
                        for mqmgr_name, mqmgr_data in mqmgr_dict.items():
                            stats['organizations'][org_name]['mqmanagers'] += 1

                            # Track MQ manager details
                            stats['mqmanagers'][mqmgr_name] = {
                                'org': org_name,
                                'dept': dept_name,
                                'app': app_name,
                                'is_gateway': mqmgr_data.get('IsGateway', False)
                            }

                            # Track gateways
                            if mqmgr_data.get('IsGateway', False):
                                stats['gateways'].append({
                                    'name': mqmgr_name,
                                    'scope': mqmgr_data.get('GatewayScope', ''),
                                    'org': org_name,
                                    'dept': dept_name
                                })

                            # Track queues
                            stats['queues']['qlocal'] += mqmgr_data.get('qlocal_count', 0)
                            stats['queues']['qremote'] += mqmgr_data.get('qremote_count', 0)
                            stats['queues']['qalias'] += mqmgr_data.get('qalias_count', 0)

                            # Analyze connections by type
                            for target in mqmgr_data.get('outbound', []):
                                target_info = stats['mqmanagers'].get(target, {})
                                if target_info.get('org') == org_name:
                                    if target_info.get('dept') == dept_name:
                                        stats['connections']['internal'] += 1
                                    else:
                                        stats['connections']['cross_dept'] += 1
                                else:
                                    stats['connections']['cross_org'] += 1

        stats['queues']['total'] = sum([stats['queues']['qlocal'], stats['queues']['qremote'], stats['queues']['qalias']])

        return stats

    def _analyze_dependencies(self) -> Dict:
        """Analyze inter-application and inter-organizational dependencies."""
        dependencies = {
            'org_to_org': defaultdict(set),
            'dept_to_dept': defaultdict(set),
            'app_to_app': defaultdict(set),
            'critical_paths': []
        }

        for mqmgr_name, mqmgr_info in self.stats['mqmanagers'].items():
            source_org = mqmgr_info['org']
            source_dept = mqmgr_info['dept']
            source_app = mqmgr_info['app']

            # Get connections from enriched data
            for org_name, org_data in self.data.items():
                if not isinstance(org_data, dict) or '_departments' not in org_data:
                    continue

                for dept_name, dept_data in org_data['_departments'].items():
                    for biz_ownr, applications in dept_data.items():
                        for app_name, mqmgr_dict in applications.items():
                            if mqmgr_name in mqmgr_dict:
                                mqmgr_data = mqmgr_dict[mqmgr_name]
                                all_targets = mqmgr_data.get('outbound', []) + mqmgr_data.get('outbound_extra', [])

                                for target in all_targets:
                                    if target in self.stats['mqmanagers']:
                                        target_info = self.stats['mqmanagers'][target]
                                        target_org = target_info['org']
                                        target_dept = target_info['dept']
                                        target_app = target_info['app']

                                        # Track organizational dependencies
                                        if source_org != target_org:
                                            dependencies['org_to_org'][source_org].add(target_org)

                                        # Track departmental dependencies
                                        if source_dept != target_dept:
                                            dep_key = f"{source_org}/{source_dept}"
                                            dep_target = f"{target_org}/{target_dept}"
                                            dependencies['dept_to_dept'][dep_key].add(dep_target)

                                        # Track application dependencies
                                        if source_app != target_app and not source_app.startswith('Gateway ('):
                                            dependencies['app_to_app'][source_app].add(target_app)

        return dependencies

    def _identify_integration_patterns(self) -> Dict:
        """Identify integration patterns and antipatterns."""
        patterns = {
            'gateway_mediated': 0,
            'direct_integration': 0,
            'hub_and_spoke': [],
            'point_to_point': [],
            'complexity_score': {}
        }

        for mqmgr_name, mqmgr_info in self.stats['mqmanagers'].items():
            # Calculate connection complexity
            for org_name, org_data in self.data.items():
                if not isinstance(org_data, dict) or '_departments' not in org_data:
                    continue

                for dept_name, dept_data in org_data['_departments'].items():
                    for biz_ownr, applications in dept_data.items():
                        for app_name, mqmgr_dict in applications.items():
                            if mqmgr_name in mqmgr_dict:
                                mqmgr_data = mqmgr_dict[mqmgr_name]
                                total_connections = (
                                    len(mqmgr_data.get('inbound', [])) +
                                    len(mqmgr_data.get('outbound', [])) +
                                    len(mqmgr_data.get('inbound_extra', [])) +
                                    len(mqmgr_data.get('outbound_extra', []))
                                )

                                if total_connections > 0:
                                    patterns['complexity_score'][mqmgr_name] = total_connections

                                    if mqmgr_info['is_gateway']:
                                        patterns['gateway_mediated'] += total_connections
                                        if total_connections > 10:
                                            patterns['hub_and_spoke'].append({
                                                'gateway': mqmgr_name,
                                                'connections': total_connections
                                            })
                                    else:
                                        patterns['direct_integration'] += total_connections

        return patterns

    def generate_confluence_markup(self, output_file: Path):
        """Generate Confluence-compatible markup documentation."""
        doc = []

        # Title and metadata
        doc.append("{panel:title=Document Control|borderStyle=solid}")
        doc.append(f"*Document Type:* Enterprise Architecture - Integration View")
        doc.append(f"*Generated:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        doc.append(f"*Scope:* MQ Middleware Topology")
        doc.append(f"*Classification:* Internal")
        doc.append("{panel}\n")

        # Executive Summary
        doc.append("h1. Executive Summary\n")
        doc.append("{info:title=Key Metrics}")
        doc.append(f"*Organizations:* {len(self.stats['organizations'])}")
        doc.append(f"*Departments:* {len(self.stats['departments'])}")
        doc.append(f"*MQ Managers:* {len(self.stats['mqmanagers'])}")
        doc.append(f"*Gateway Infrastructure:* {len(self.stats['gateways'])} ({len([g for g in self.stats['gateways'] if g['scope']=='Internal'])} Internal / {len([g for g in self.stats['gateways'] if g['scope']=='External'])} External)")
        doc.append(f"*Total Message Queues:* {self.stats['queues']['total']}")
        doc.append("{info}\n")

        # Architecture Principles
        doc.append("h1. Architecture Principles\n")
        doc.append("h2. Integration Architecture\n")
        doc.append("The MQ middleware infrastructure follows these architectural principles:\n")
        doc.append("# *Gateway-Mediated Integration* - Cross-organizational communication is mediated through designated gateway MQ managers")
        doc.append("# *Hierarchical Organization* - Components are organized by Organization → Department → Application")
        doc.append("# *Queue-Based Messaging* - Asynchronous messaging using IBM MQ queues (Local, Remote, Alias)")
        doc.append("# *Separation of Concerns* - Internal vs External gateways for different integration scopes\n")

        # Organizational Landscape
        doc.append("h1. Organizational Landscape\n")
        for org_name, org_info in sorted(self.stats['organizations'].items()):
            doc.append(f"h2. {org_name} ({org_info['type']})\n")
            doc.append("||Metric||Value||")
            doc.append(f"|Departments|{len(org_info['departments'])}|")
            doc.append(f"|MQ Managers|{org_info['mqmanagers']}|")
            doc.append("")

        # Gateway Infrastructure (Critical Component)
        doc.append("h1. Gateway Infrastructure\n")
        doc.append("{warning:title=Critical Infrastructure Component}")
        doc.append("Gateways are critical integration points. Single points of failure are highlighted below.")
        doc.append("{warning}\n")

        doc.append("h2. Internal Gateways")
        doc.append("||Gateway||Organization||Department||Purpose||")
        internal_gateways = [g for g in self.stats['gateways'] if g['scope'] == 'Internal']
        for gw in sorted(internal_gateways, key=lambda x: x['name']):
            doc.append(f"|{gw['name']}|{gw['org']}|{gw['dept']}|Inter-departmental communication|")
        if not internal_gateways:
            doc.append("|_No internal gateways configured_| | | |")
        doc.append("")

        doc.append("h2. External Gateways")
        doc.append("||Gateway||Organization||Department||Purpose||")
        external_gateways = [g for g in self.stats['gateways'] if g['scope'] == 'External']
        for gw in sorted(external_gateways, key=lambda x: x['name']):
            doc.append(f"|{gw['name']}|{gw['org']}|{gw['dept']}|External organization integration|")
        if not external_gateways:
            doc.append("|_No external gateways configured_| | | |")
        doc.append("")

        # Integration Patterns
        doc.append("h1. Integration Patterns\n")
        doc.append("h2. Pattern Analysis\n")
        doc.append("||Pattern||Count||Assessment||")
        doc.append(f"|Gateway-Mediated Integration|{self.integration_patterns['gateway_mediated']}|{{color:green}}✓ Best Practice{{color}}|")
        doc.append(f"|Direct Point-to-Point|{self.integration_patterns['direct_integration']}|{{color:orange}}⚠ Monitor Complexity{{color}}|")
        doc.append("")

        if self.integration_patterns['hub_and_spoke']:
            doc.append("h2. Hub-and-Spoke Patterns (High Connection Count)")
            doc.append("||Gateway||Connections||Risk||")
            for hub in sorted(self.integration_patterns['hub_and_spoke'], key=lambda x: x['connections'], reverse=True):
                risk = "{color:red}High{color}" if hub['connections'] > 20 else "{color:orange}Medium{color}"
                doc.append(f"|{hub['gateway']}|{hub['connections']}|{risk}|")
            doc.append("")

        # Dependency Analysis
        doc.append("h1. Dependency Analysis\n")

        doc.append("h2. Cross-Organizational Dependencies\n")
        if self.dependencies['org_to_org']:
            doc.append("||Source Organization||Target Organizations||Dependency Count||")
            for source_org, target_orgs in sorted(self.dependencies['org_to_org'].items()):
                target_list = ', '.join(sorted(target_orgs))
                doc.append(f"|{source_org}|{target_list}|{len(target_orgs)}|")
        else:
            doc.append("{tip}No cross-organizational dependencies detected{tip}")
        doc.append("")

        doc.append("h2. Application Dependencies\n")
        if self.dependencies['app_to_app']:
            doc.append("||Source Application||Dependent Applications||")
            for source_app, target_apps in sorted(self.dependencies['app_to_app'].items()):
                if not source_app.startswith('Gateway ('):
                    target_list = ', '.join([t for t in sorted(target_apps) if not t.startswith('Gateway (')])
                    if target_list:
                        doc.append(f"|{source_app}|{target_list}|")
        doc.append("")

        # Technology Stack
        doc.append("h1. Technology Stack\n")
        doc.append("||Component||Technology||Count||")
        doc.append(f"|Message Broker|IBM MQ (Message Queue Managers)|{len(self.stats['mqmanagers'])}|")
        doc.append(f"|Local Queues|IBM MQ QLocal|{self.stats['queues']['qlocal']}|")
        doc.append(f"|Remote Queues|IBM MQ QRemote|{self.stats['queues']['qremote']}|")
        doc.append(f"|Alias Queues|IBM MQ QAlias|{self.stats['queues']['qalias']}|")
        doc.append(f"|Gateway Infrastructure|MQ Gateway Managers|{len(self.stats['gateways'])}|")
        doc.append("")

        # Risks and Recommendations
        doc.append("h1. Risks & Recommendations\n")

        # Identify SPOFs
        spof_count = 0
        for gw in self.stats['gateways']:
            # Check if this is the only gateway of its type
            same_scope_gateways = [g for g in self.stats['gateways'] if g['scope'] == gw['scope'] and g['org'] == gw['org']]
            if len(same_scope_gateways) == 1:
                spof_count += 1

        if spof_count > 0:
            doc.append("{color:red}h2. High Priority{color}\n")
            doc.append(f"# *Single Points of Failure:* {spof_count} gateway(s) identified without redundancy")
            doc.append(f"# *Recommendation:* Implement redundant gateway infrastructure for high-availability\n")

        # Connection complexity
        high_complexity = [mqmgr for mqmgr, score in self.integration_patterns['complexity_score'].items() if score > 15]
        if high_complexity:
            doc.append("{color:orange}h2. Medium Priority{color}\n")
            doc.append(f"# *Integration Complexity:* {len(high_complexity)} MQ manager(s) with >15 connections")
            doc.append(f"# *Recommendation:* Review integration patterns and consider simplification\n")

        # Best practices
        doc.append("h2. Best Practices\n")
        doc.append("# Regular gateway health monitoring and capacity planning")
        doc.append("# Maintain gateway redundancy for critical integration paths")
        doc.append("# Document all cross-organizational dependencies")
        doc.append("# Implement change detection to track topology evolution")
        doc.append("# Review and optimize high-complexity integration points\n")

        # Appendix
        doc.append("h1. Appendix\n")
        doc.append("h2. Generated Artifacts\n")
        doc.append("* Hierarchical Topology Diagram: {{mq_topology.pdf}}")
        doc.append("* Application Connection Diagrams: {{application_diagrams/}}")
        doc.append("* Individual MQ Manager Diagrams: {{individual_diagrams/}}")
        doc.append("* Gateway Analytics Report: {{gateway_analytics_*.html}}")
        doc.append("* Change Detection Report: {{change_report_*.html}}")
        doc.append("* Excel Inventory: {{mqcmdb_inventory_*.xlsx}}")
        doc.append("")

        doc.append("---")
        doc.append("{panel:bgColor=#f0f0f0}")
        doc.append("_This Enterprise Architecture documentation was automatically generated by MQ CMDB Hierarchical Automation System_")
        doc.append("{panel}")

        # Write file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(doc))

        print(f"✓ EA Documentation (Confluence) generated: {output_file}")
        return True
