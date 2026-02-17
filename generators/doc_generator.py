
"""
Enterprise Architecture Documentation Generator - TOGAF Aligned

Generates comprehensive EA documentation following TOGAF framework:
- Architecture Vision
- Business Architecture
- Information Systems Architecture (Data & Application)
- Technology Architecture
- Architecture Principles
- Gap Analysis & Opportunities
- Risk Assessment (RAID)
- Architecture Roadmap & Recommendations

Reference: TOGAF 9.2 Architecture Content Framework

Subclasses ``ConfluenceDocGenerator`` — loaded from the shared scripts
directory in production, falling back to the local ``scripts/common/``
copy during development.
"""

import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple
from datetime import datetime
from collections import defaultdict
from utils.logging_config import get_logger

# Shared scripts directory (same convention as confluence_shim.py)
_SHARED_SCRIPTS_DIR = os.environ.get("SHARED_SCRIPTS_DIR", r"C:/Users/BABED2P/Documents/WORKSPACE/Scripts")
if _SHARED_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SHARED_SCRIPTS_DIR)

try:
    from confluence_doc_generator import ConfluenceDocGenerator
except ImportError:
    from scripts.common.confluence_doc_generator import ConfluenceDocGenerator

logger = get_logger("generators.doc_generator")


class EADocumentationGenerator(ConfluenceDocGenerator):
    """Generate TOGAF-aligned Enterprise Architecture documentation for MQ CMDB topology."""

    def __init__(self, enriched_data: Dict):
        """
        Initialize EA documentation generator.

        Args:
            enriched_data: Enriched hierarchical MQ CMDB data

        Raises:
            ValueError: If enriched_data is not a dictionary
        """
        if not isinstance(enriched_data, dict):
            raise ValueError(f"enriched_data must be a dict, got {type(enriched_data).__name__}")
        self.data = enriched_data
        self.stats = self._calculate_statistics()
        self.dependencies = self._analyze_dependencies()
        self.integration_patterns = self._identify_integration_patterns()
        self.capabilities = self._map_business_capabilities()
        self.risks = self._assess_risks()
        self.maturity = self._assess_maturity()

    def _calculate_statistics(self) -> Dict:
        """Calculate comprehensive statistics."""
        stats = {
            'organizations': {},
            'departments': set(),
            'biz_owners': set(),
            'applications': set(),
            'mqmanagers': {},
            'gateways': [],
            'connections': {'internal': 0, 'cross_dept': 0, 'cross_org': 0, 'external': 0},
            'queues': {'qlocal': 0, 'qremote': 0, 'qalias': 0, 'total': 0}
        }
        seen_gateways = set()

        for org_name, org_data in self.data.items():
            if not isinstance(org_data, dict) or '_departments' not in org_data:
                continue

            org_type = org_data.get('_org_type', 'Internal')
            stats['organizations'][org_name] = {
                'type': org_type,
                'departments': set(),
                'mqmanagers': 0,
                'applications': set()
            }

            for dept_name, dept_data in org_data['_departments'].items():
                stats['departments'].add(dept_name)
                stats['organizations'][org_name]['departments'].add(dept_name)

                for biz_ownr, applications in dept_data.items():
                    stats['biz_owners'].add(biz_ownr)

                    for app_name, mqmgr_dict in applications.items():
                        if not app_name.startswith('Gateway (') and app_name != 'No Application':
                            stats['applications'].add(app_name)
                            stats['organizations'][org_name]['applications'].add(app_name)

                        for mqmgr_name, mqmgr_data in mqmgr_dict.items():
                            stats['organizations'][org_name]['mqmanagers'] += 1

                            stats['mqmanagers'][mqmgr_name] = {
                                'org': org_name,
                                'org_type': org_type,
                                'dept': dept_name,
                                'biz_ownr': biz_ownr,
                                'app': app_name,
                                'is_gateway': mqmgr_data.get('IsGateway', False),
                                'gateway_scope': mqmgr_data.get('GatewayScope', ''),
                                'qlocal': mqmgr_data.get('qlocal_count', 0),
                                'qremote': mqmgr_data.get('qremote_count', 0),
                                'qalias': mqmgr_data.get('qalias_count', 0),
                                'inbound': mqmgr_data.get('inbound', []),
                                'outbound': mqmgr_data.get('outbound', []),
                                'inbound_extra': mqmgr_data.get('inbound_extra', []),
                                'outbound_extra': mqmgr_data.get('outbound_extra', [])
                            }

                            if mqmgr_data.get('IsGateway', False) and mqmgr_name not in seen_gateways:
                                seen_gateways.add(mqmgr_name)
                                stats['gateways'].append({
                                    'name': mqmgr_name,
                                    'scope': mqmgr_data.get('GatewayScope', ''),
                                    'org': org_name,
                                    'dept': dept_name
                                })

                            stats['queues']['qlocal'] += mqmgr_data.get('qlocal_count', 0)
                            stats['queues']['qremote'] += mqmgr_data.get('qremote_count', 0)
                            stats['queues']['qalias'] += mqmgr_data.get('qalias_count', 0)

                            for target in mqmgr_data.get('outbound', []):
                                target_info = stats['mqmanagers'].get(target, {})
                                if target_info.get('org') == org_name:
                                    if target_info.get('dept') == dept_name:
                                        stats['connections']['internal'] += 1
                                    else:
                                        stats['connections']['cross_dept'] += 1
                                else:
                                    stats['connections']['cross_org'] += 1

                            stats['connections']['external'] += len(mqmgr_data.get('outbound_extra', []))

        stats['queues']['total'] = sum([stats['queues']['qlocal'], stats['queues']['qremote'], stats['queues']['qalias']])
        return stats

    def _analyze_dependencies(self) -> Dict:
        """Analyze inter-application and inter-organizational dependencies."""
        dependencies = {
            'org_to_org': defaultdict(set),
            'dept_to_dept': defaultdict(set),
            'app_to_app': defaultdict(set),
            'critical_paths': [],
            'external_partners': set()
        }

        for mqmgr_name, mqmgr_info in self.stats['mqmanagers'].items():
            source_org = mqmgr_info['org']
            source_dept = mqmgr_info['dept']
            source_app = mqmgr_info['app']

            all_targets = mqmgr_info.get('outbound', []) + mqmgr_info.get('outbound_extra', [])

            for target in all_targets:
                if target in self.stats['mqmanagers']:
                    target_info = self.stats['mqmanagers'][target]
                    target_org = target_info['org']
                    target_dept = target_info['dept']
                    target_app = target_info['app']

                    if source_org != target_org:
                        dependencies['org_to_org'][source_org].add(target_org)
                        if target_info.get('org_type') == 'External':
                            dependencies['external_partners'].add(target_org)

                    if source_dept != target_dept:
                        dep_key = f"{source_org}/{source_dept}"
                        dep_target = f"{target_org}/{target_dept}"
                        dependencies['dept_to_dept'][dep_key].add(dep_target)

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
            'complexity_score': {},
            'high_fanout': [],
            'high_fanin': []
        }

        for mqmgr_name, mqmgr_info in self.stats['mqmanagers'].items():
            inbound_count = len(mqmgr_info.get('inbound', [])) + len(mqmgr_info.get('inbound_extra', []))
            outbound_count = len(mqmgr_info.get('outbound', [])) + len(mqmgr_info.get('outbound_extra', []))
            total_connections = inbound_count + outbound_count

            if total_connections > 0:
                patterns['complexity_score'][mqmgr_name] = total_connections

                if mqmgr_info.get('is_gateway'):
                    patterns['gateway_mediated'] += total_connections
                    if total_connections > 10:
                        patterns['hub_and_spoke'].append({
                            'gateway': mqmgr_name,
                            'connections': total_connections,
                            'scope': mqmgr_info.get('gateway_scope', '')
                        })
                else:
                    patterns['direct_integration'] += total_connections

                if outbound_count > 8:
                    patterns['high_fanout'].append({'mqmgr': mqmgr_name, 'count': outbound_count})
                if inbound_count > 8:
                    patterns['high_fanin'].append({'mqmgr': mqmgr_name, 'count': inbound_count})

        return patterns

    def _map_business_capabilities(self) -> Dict:
        """Map MQ infrastructure to business capabilities."""
        capabilities = {
            'integration_capability': {
                'internal_messaging': len([m for m in self.stats['mqmanagers'].values() if not m['is_gateway']]),
                'gateway_services': len(self.stats['gateways']),
                'external_connectivity': len([g for g in self.stats['gateways'] if g['scope'] == 'External'])
            },
            'by_department': defaultdict(lambda: {'apps': set(), 'mqmanagers': 0, 'queues': 0}),
            'by_application': {}
        }

        for mqmgr_name, info in self.stats['mqmanagers'].items():
            dept = info['dept']
            app = info['app']
            capabilities['by_department'][dept]['mqmanagers'] += 1
            capabilities['by_department'][dept]['queues'] += info['qlocal'] + info['qremote'] + info['qalias']
            if app and not app.startswith('Gateway ('):
                capabilities['by_department'][dept]['apps'].add(app)

            if app and not app.startswith('Gateway (') and app != 'No Application':
                if app not in capabilities['by_application']:
                    capabilities['by_application'][app] = {
                        'mqmanagers': [],
                        'dept': info['dept'],
                        'org': info['org'],
                        'biz_ownr': info['biz_ownr'],
                        'total_queues': 0,
                        'connections': 0
                    }
                capabilities['by_application'][app]['mqmanagers'].append(mqmgr_name)
                capabilities['by_application'][app]['total_queues'] += info['qlocal'] + info['qremote'] + info['qalias']
                capabilities['by_application'][app]['connections'] += len(info.get('outbound', [])) + len(info.get('inbound', []))

        return capabilities

    def _assess_risks(self) -> Dict:
        """Comprehensive risk assessment following RAID framework."""
        risks = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': [],
            'assumptions': [],
            'issues': [],
            'dependencies': []
        }

        # SPOF Analysis
        internal_gateways = [g for g in self.stats['gateways'] if g['scope'] == 'Internal']
        external_gateways = [g for g in self.stats['gateways'] if g['scope'] == 'External']

        orgs_with_single_internal_gw = defaultdict(list)
        orgs_with_single_external_gw = defaultdict(list)

        for gw in internal_gateways:
            orgs_with_single_internal_gw[gw['org']].append(gw['name'])
        for gw in external_gateways:
            orgs_with_single_external_gw[gw['org']].append(gw['name'])

        for org, gateways in orgs_with_single_internal_gw.items():
            if len(gateways) == 1:
                risks['critical'].append({
                    'id': f'SPOF-INT-{org[:3].upper()}',
                    'category': 'Single Point of Failure',
                    'description': f'Single internal gateway ({gateways[0]}) for {org}',
                    'impact': 'Complete loss of inter-departmental messaging',
                    'mitigation': 'Implement redundant gateway with failover'
                })

        for org, gateways in orgs_with_single_external_gw.items():
            if len(gateways) == 1:
                risks['critical'].append({
                    'id': f'SPOF-EXT-{org[:3].upper()}',
                    'category': 'Single Point of Failure',
                    'description': f'Single external gateway ({gateways[0]}) for {org}',
                    'impact': 'Complete loss of external partner connectivity',
                    'mitigation': 'Implement redundant external gateway'
                })

        # Complexity risks
        for mqmgr, score in self.integration_patterns['complexity_score'].items():
            if score > 25:
                risks['high'].append({
                    'id': f'CMPLX-{mqmgr[:8].upper()}',
                    'category': 'Integration Complexity',
                    'description': f'{mqmgr} has {score} connections',
                    'impact': 'Difficult to maintain, test, and troubleshoot',
                    'mitigation': 'Consider decomposition or introducing mediation layer'
                })
            elif score > 15:
                risks['medium'].append({
                    'id': f'CMPLX-{mqmgr[:8].upper()}',
                    'category': 'Integration Complexity',
                    'description': f'{mqmgr} has {score} connections',
                    'impact': 'Increased maintenance overhead',
                    'mitigation': 'Monitor and plan for refactoring'
                })

        # Concentration risk
        for dept_info in self.capabilities['by_department'].values():
            if dept_info['mqmanagers'] > 20:
                risks['medium'].append({
                    'id': 'CONC-DEPT',
                    'category': 'Concentration Risk',
                    'description': 'High concentration of MQ managers in single department',
                    'impact': 'Department-wide outage affects many integrations',
                    'mitigation': 'Review disaster recovery and failover procedures'
                })
                break

        # External dependency risks
        if self.dependencies['external_partners']:
            risks['dependencies'].append({
                'id': 'DEP-EXT',
                'description': f"External partner dependencies: {', '.join(self.dependencies['external_partners'])}",
                'owner': 'Integration Team',
                'status': 'Active'
            })

        # Assumptions
        risks['assumptions'].append({
            'id': 'ASM-001',
            'description': 'All MQ managers are configured with standard security policies',
            'owner': 'Security Team',
            'validation_date': 'TBD'
        })
        risks['assumptions'].append({
            'id': 'ASM-002',
            'description': 'Network connectivity between all components is reliable',
            'owner': 'Network Team',
            'validation_date': 'TBD'
        })

        return risks

    def _assess_maturity(self) -> Dict:
        """Assess architecture maturity level."""
        maturity = {
            'overall_level': 0,
            'dimensions': {},
            'recommendations': []
        }

        # Gateway coverage
        if len(self.stats['gateways']) > 0:
            maturity['dimensions']['gateway_adoption'] = 3
        else:
            maturity['dimensions']['gateway_adoption'] = 1
            maturity['recommendations'].append('Implement gateway pattern for cross-boundary integrations')

        # Redundancy
        redundant_gateways = 0
        for org in self.stats['organizations']:
            internal_count = len([g for g in self.stats['gateways'] if g['org'] == org and g['scope'] == 'Internal'])
            if internal_count >= 2:
                redundant_gateways += 1

        if redundant_gateways > 0:
            maturity['dimensions']['high_availability'] = 3
        else:
            maturity['dimensions']['high_availability'] = 1
            maturity['recommendations'].append('Implement redundant gateways for high availability')

        # Integration pattern maturity
        gateway_ratio = self.integration_patterns['gateway_mediated'] / max(1, self.integration_patterns['direct_integration'] + self.integration_patterns['gateway_mediated'])
        if gateway_ratio > 0.6:
            maturity['dimensions']['integration_patterns'] = 4
        elif gateway_ratio > 0.3:
            maturity['dimensions']['integration_patterns'] = 3
        else:
            maturity['dimensions']['integration_patterns'] = 2
            maturity['recommendations'].append('Increase use of gateway-mediated integrations')

        # Documentation (self-referential - we're generating it!)
        maturity['dimensions']['documentation'] = 4

        # Calculate overall
        maturity['overall_level'] = round(sum(maturity['dimensions'].values()) / len(maturity['dimensions']), 1)

        return maturity

    # ------------------------------------------------------------------ #
    #  Backward-compatible aliases for base class markup helpers
    # ------------------------------------------------------------------ #

    _styled_panel = staticmethod(ConfluenceDocGenerator.styled_panel)
    _status_lozenge = staticmethod(ConfluenceDocGenerator.status_lozenge)
    _expandable = staticmethod(ConfluenceDocGenerator.expandable)

    # ------------------------------------------------------------------ #
    #  ConfluenceDocGenerator abstract method implementations
    # ------------------------------------------------------------------ #

    def build_header(self) -> List[str]:
        return self._generate_document_header()

    def build_toc(self) -> List[str]:
        return self._generate_toc()

    def get_sections(self) -> List[Tuple[str, Callable[[], List[str]]]]:
        return [
            ("Architecture Vision",      self._generate_architecture_vision),
            ("Stakeholder Analysis",     self._generate_stakeholder_analysis),
            ("Architecture Principles",  self._generate_architecture_principles),
            ("Business Architecture",    self._generate_business_architecture),
            ("Data Architecture",        self._generate_data_architecture),
            ("Application Architecture", self._generate_application_architecture),
            ("Technology Architecture",  self._generate_technology_architecture),
            ("Integration Patterns",     self._generate_integration_patterns),
            ("Gap Analysis",             self._generate_gap_analysis),
            ("Risk Assessment",          self._generate_risk_assessment),
            ("Architecture Roadmap",     self._generate_roadmap),
            ("Appendices",               self._generate_appendices),
        ]

    def build_footer(self) -> List[str]:
        return self._generate_footer()

    # ------------------------------------------------------------------ #
    #  Public API (backward-compatible entry point)
    # ------------------------------------------------------------------ #

    def generate_confluence_markup(self, output_file: Path) -> bool:
        """Generate comprehensive TOGAF-aligned Confluence documentation."""
        result = self.generate(output_file)
        logger.info(f"✓ EA Documentation (TOGAF-aligned) generated: {output_file}")
        return result

    def _generate_document_header(self) -> List[str]:
        """Generate document control header."""
        header_content = [
            "h1. MQ Integration Architecture",
            "",
            "||Document Property||Value||",
            "|*Document Type*|Enterprise Architecture - Integration Domain|",
            f"|*Generated*|{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}|",
            "|*Framework*|TOGAF 9.2 Architecture Content Framework|",
            "|*Scope*|IBM MQ Middleware Integration Topology|",
            f"|*Classification*|{self._status_lozenge('Internal Use Only', 'Blue')}|",
            f"|*Status*|{self._status_lozenge('Current State Architecture', 'Green')}|",
        ]
        lines = self._styled_panel(
            "TOGAF Architecture Document",
            header_content,
            bg_color="#f7f9fb",
            title_bg="#1a3c5e",
            title_color="#ffffff",
            border_color="#1a3c5e",
        )
        lines.extend([
            "",
            "----",
            "",
        ])
        return lines

    def _generate_toc(self) -> List[str]:
        """Generate table of contents as a styled navigation panel."""
        nav_content = [
            "{section}",
            "{column:width=50%}",
            "",
            "||Architecture Foundation||",
            f"| *1* | [Architecture Vision|#architecture-vision] |",
            f"| *2* | [Stakeholder Analysis|#stakeholder-analysis] |",
            f"| *3* | [Architecture Principles|#architecture-principles] |",
            "",
            "||Architecture Domains||",
            f"| *4* | [Business Architecture|#business-architecture] |",
            f"| *5* | [Data Architecture|#data-architecture] |",
            f"| *6* | [Application Architecture|#application-architecture] |",
            "{column}",
            "{column:width=50%}",
            "",
            "||Infrastructure & Patterns||",
            f"| *7* | [Technology Architecture|#technology-architecture] |",
            f"| *8* | [Integration Patterns|#integration-patterns] |",
            "",
            "||Governance & Planning||",
            f"| *9*  | [Gap Analysis|#gap-analysis] |",
            f"| *10* | [Risk Assessment|#risk-assessment] |",
            f"| *11* | [Architecture Roadmap|#architecture-roadmap] |",
            f"| *12* | [Appendices|#appendices] |",
            "{column}",
            "{section}",
        ]
        lines = self._styled_panel(
            "Table of Contents",
            nav_content,
            bg_color="#f7f9fb",
            title_bg="#1a3c5e",
            title_color="#ffffff",
            border_color="#1a3c5e",
        )
        lines.append("")
        return lines

    def _generate_architecture_vision(self) -> List[str]:
        """Generate Architecture Vision section."""
        internal_gw = len([g for g in self.stats['gateways'] if g['scope'] == 'Internal'])
        external_gw = len([g for g in self.stats['gateways'] if g['scope'] == 'External'])
        internal_orgs = len([o for o, d in self.stats['organizations'].items() if d['type'] == 'Internal'])
        external_orgs = len([o for o, d in self.stats['organizations'].items() if d['type'] == 'External'])

        return [
            "{anchor:architecture-vision}",
            "h1. 1. Architecture Vision",
            "",
            "h2. 1.1 Executive Summary",
            "",
            "{info:title=Architecture Overview}",
            "This document describes the current-state Enterprise Architecture for the MQ-based integration infrastructure. It follows the TOGAF Architecture Content Framework to provide a comprehensive view across business, data, application, and technology domains.",
            "{info}",
            "",
            "h2. 1.2 Key Metrics Dashboard",
            "",
            "{section}",
            "{column:width=33%}",
            *self._styled_panel("Organizations", [
                f"h2. {len(self.stats['organizations'])}",
                f"{internal_orgs} Internal, {external_orgs} External",
            ], bg_color="#e8f5e9", title_bg="#2e7d32", title_color="#fff", border_color="#a5d6a7"),
            "{column}",
            "{column:width=33%}",
            *self._styled_panel("Applications", [
                f"h2. {len(self.stats['applications'])}",
                "Integrated via MQ",
            ], bg_color="#e3f2fd", title_bg="#1565c0", title_color="#fff", border_color="#90caf9"),
            "{column}",
            "{column:width=33%}",
            *self._styled_panel("MQ Managers", [
                f"h2. {len(self.stats['mqmanagers'])}",
                f"{internal_gw + external_gw} Gateways",
            ], bg_color="#fff3e0", title_bg="#e65100", title_color="#fff", border_color="#ffcc80"),
            "{column}",
            "{section}",
            "{section}",
            "{column:width=33%}",
            *self._styled_panel("Message Queues", [
                f"h2. {self.stats['queues']['total']:,}",
                f"Local: {self.stats['queues']['qlocal']:,} | Remote: {self.stats['queues']['qremote']:,} | Alias: {self.stats['queues']['qalias']:,}",
            ], bg_color="#fce4ec", title_bg="#c62828", title_color="#fff", border_color="#ef9a9a"),
            "{column}",
            "{column:width=33%}",
            *self._styled_panel("Departments", [
                f"h2. {len(self.stats['departments'])}",
                "Across all organizations",
            ], bg_color="#f3e5f5", title_bg="#6a1b9a", title_color="#fff", border_color="#ce93d8"),
            "{column}",
            "{column:width=33%}",
            *self._styled_panel("Business Owners", [
                f"h2. {len(self.stats['biz_owners'])}",
                "Application stakeholders",
            ], bg_color="#e0f2f1", title_bg="#00695c", title_color="#fff", border_color="#80cbc4"),
            "{column}",
            "{section}",
            "",
            "h2. 1.3 Scope and Boundaries",
            "",
            "||Aspect||In Scope||Out of Scope||",
            "|*Technology*|IBM MQ Queue Managers, Queues, Channels|MQ Client applications, JMS implementations|",
            "|*Integration*|Message-based integrations, Gateway patterns|API integrations, File transfers|",
            "|*Organizations*|All entities with MQ infrastructure|Non-MQ integration patterns|",
            "|*Lifecycle*|Current state architecture|Future state design (see Roadmap)|",
            "",
            "h2. 1.4 Architecture Goals",
            "",
            "{quote}",
            "# *Reliability* - Ensure message delivery guarantees across all integration paths",
            "# *Scalability* - Support growing message volumes and new integrations",
            "# *Security* - Protect message content and control access to queues",
            "# *Maintainability* - Enable efficient operations and change management",
            "# *Visibility* - Provide clear documentation and monitoring capabilities",
            "{quote}",
            "",
            "----",
            ""
        ]

    def _generate_stakeholder_analysis(self) -> List[str]:
        """Generate Stakeholder Analysis section."""
        lines = [
            "{anchor:stakeholder-analysis}",
            "h1. 2. Stakeholder Analysis",
            "",
            "h2. 2.1 Stakeholder Map",
            "",
            "||Stakeholder Group||Concerns||Architecture Views||",
            "|*Executive Leadership*|Business continuity, Cost efficiency|Architecture Vision, Risk Assessment|",
            "|*Enterprise Architects*|Standards compliance, Integration patterns|All sections|",
            "|*Solution Architects*|Application integration, Data flows|Application & Data Architecture|",
            "|*Operations Team*|Availability, Performance, Monitoring|Technology Architecture, Risk Assessment|",
            "|*Development Teams*|Queue configurations, Message formats|Application Architecture, Integration Patterns|",
            "|*Security Team*|Access control, Data protection|Technology Architecture, Risk Assessment|",
            "|*Business Owners*|Application availability, SLAs|Business Architecture|",
            "",
            "h2. 2.2 Business Owner Distribution",
            "",
        ]

        # Group by business owner
        biz_owner_stats = defaultdict(lambda: {'dept': '', 'apps': set(), 'mqmgrs': 0})
        for mqmgr_name, info in self.stats['mqmanagers'].items():
            biz_ownr = info.get('biz_ownr', 'Unknown')
            biz_owner_stats[biz_ownr]['dept'] = info.get('dept', '')
            if info['app'] and not info['app'].startswith('Gateway ('):
                biz_owner_stats[biz_ownr]['apps'].add(info['app'])
            biz_owner_stats[biz_ownr]['mqmgrs'] += 1

        biz_table = ["||Business Owner||Department||Applications||MQ Managers||"]
        for biz_ownr, stats in sorted(biz_owner_stats.items()):
            if biz_ownr != 'Unknown':
                biz_table.append(f"|{biz_ownr}|{stats['dept']}|{len(stats['apps'])}|{stats['mqmgrs']}|")

        lines.extend(self._expandable(
            f"Business Owner Distribution ({len(biz_owner_stats)} owners)", biz_table
        ))

        lines.extend(["", "----", ""])
        return lines

    def _generate_architecture_principles(self) -> List[str]:
        """Generate Architecture Principles section."""
        principles = [
            {
                "id": "PRIN-01", "name": "Gateway-Mediated Integration",
                "statement": "All cross-organizational and cross-departmental integrations SHOULD be mediated through designated gateway MQ managers.",
                "rationale": "Centralized integration points provide better control, monitoring, and security enforcement.",
                "implications": [
                    "Gateway infrastructure must be highly available",
                    "All external connections must route through external gateways",
                    "Direct point-to-point connections should be reviewed for migration",
                ],
            },
            {
                "id": "PRIN-02", "name": "Asynchronous Messaging",
                "statement": "Message-based integrations SHALL use asynchronous, guaranteed delivery patterns.",
                "rationale": "Asynchronous messaging provides loose coupling, resilience, and temporal decoupling between systems.",
                "implications": [
                    "Applications must handle message persistence",
                    "Dead letter queue handling must be implemented",
                    "Message ordering may require additional design consideration",
                ],
            },
            {
                "id": "PRIN-03", "name": "Hierarchical Organization",
                "statement": "MQ infrastructure SHALL be organized following the organizational hierarchy: Organization -> Department -> Business Owner -> Application.",
                "rationale": "Alignment with organizational structure enables clear ownership, governance, and change management.",
                "implications": [
                    "Naming conventions must reflect hierarchy",
                    "Access controls align with organizational boundaries",
                    "Capacity planning follows departmental structures",
                ],
            },
            {
                "id": "PRIN-04", "name": "Separation of Concerns",
                "statement": "Internal and external integration gateways SHALL be separated.",
                "rationale": "Different security, compliance, and operational requirements apply to internal vs. external integrations.",
                "implications": [
                    "Separate gateway infrastructure for internal/external",
                    "Different security policies per gateway type",
                    "External gateways require additional hardening",
                ],
            },
        ]

        lines = [
            "{anchor:architecture-principles}",
            "h1. 3. Architecture Principles",
            "",
            "{note:title=TOGAF Reference}",
            "Architecture Principles define the underlying general rules and guidelines for the use and deployment of IT resources.",
            "{note}",
            "",
            "h2. 3.1 Integration Principles",
            "",
        ]

        for p in principles:
            impl_lines = [f"* {impl}" for impl in p["implications"]]
            panel_content = [
                "{quote}",
                f"*Statement:* {p['statement']}",
                "{quote}",
                "",
                f"*Rationale:* {p['rationale']}",
                "",
                f"{{tip:title=Implications}}",
                *impl_lines,
                "{tip}",
            ]
            lines.extend(self._styled_panel(
                f"{p['id']}: {p['name']}",
                panel_content,
            ))
            lines.append("")

        lines.extend(["----", ""])
        return lines

    def _generate_business_architecture(self) -> List[str]:
        """Generate Business Architecture section."""
        lines = [
            "{anchor:business-architecture}",
            "h1. 4. Business Architecture",
            "",
            "h2. 4.1 Business Capability Model",
            "",
            "{info}",
            "The MQ infrastructure enables the following integration capabilities across the enterprise.",
            "{info}",
            "",
            "||Capability||Description||Current State||",
            f"|*Internal Messaging*|Intra-organizational message exchange|{self.capabilities['integration_capability']['internal_messaging']} MQ Managers|",
            f"|*Gateway Services*|Controlled integration points|{self.capabilities['integration_capability']['gateway_services']} Gateways|",
            f"|*External Connectivity*|Partner and external system integration|{self.capabilities['integration_capability']['external_connectivity']} External Gateways|",
            f"|*Message Routing*|Queue-based message distribution|{self.stats['queues']['qremote']:,} Remote Queues|",
            f"|*Message Transformation*|Alias and routing|{self.stats['queues']['qalias']:,} Alias Queues|",
            "",
            "h2. 4.2 Organizational Landscape",
            "",
        ]

        for org_name, org_info in sorted(self.stats['organizations'].items()):
            org_type_label = self._status_lozenge("Internal", "Green") if org_info['type'] == 'Internal' else self._status_lozenge("External", "Blue")
            org_type_text = "Internal" if org_info['type'] == 'Internal' else "External"
            org_table = [
                f"*Type:* {org_type_label}",
                "",
                "||Metric||Value||",
                f"|Departments|{len(org_info['departments'])}|",
                f"|Applications|{len(org_info['applications'])}|",
                f"|MQ Managers|{org_info['mqmanagers']}|",
            ]
            lines.extend(self._expandable(f"{org_name} ({org_type_text})", org_table))
            lines.append("")

        lines.extend([
            "h2. 4.3 Department Capability Matrix",
            "",
        ])

        dept_table = ["||Department||Applications||MQ Managers||Total Queues||"]
        for dept, info in sorted(self.capabilities['by_department'].items()):
            dept_table.append(f"|{dept}|{len(info['apps'])}|{info['mqmanagers']}|{info['queues']:,}|")

        lines.extend(self._expandable(
            f"Department Capability Matrix ({len(self.capabilities['by_department'])} departments)",
            dept_table,
        ))

        lines.extend(["", "----", ""])
        return lines

    def _generate_data_architecture(self) -> List[str]:
        """Generate Data Architecture section."""
        lines = [
            "{anchor:data-architecture}",
            "h1. 5. Data Architecture (Information Systems)",
            "",
            "h2. 5.1 Message Flow Patterns",
            "",
            "{info}",
            "This section describes how data flows through the MQ infrastructure.",
            "{info}",
            "",
            "||Flow Type||Count||Description||",
            f"|*Internal Flows*|{self.stats['connections']['internal']}|Messages within same department|",
            f"|*Cross-Department*|{self.stats['connections']['cross_dept']}|Messages between departments|",
            f"|*Cross-Organization*|{self.stats['connections']['cross_org']}|Messages between organizations|",
            f"|*External Flows*|{self.stats['connections']['external']}|Messages to/from external systems|",
            "",
            "h2. 5.2 Queue Distribution",
            "",
            "||Queue Type||Count||Purpose||",
            f"|*Local Queues (QLOCAL)*|{self.stats['queues']['qlocal']:,}|Message storage and processing|",
            f"|*Remote Queues (QREMOTE)*|{self.stats['queues']['qremote']:,}|Remote destination definitions|",
            f"|*Alias Queues (QALIAS)*|{self.stats['queues']['qalias']:,}|Queue abstraction and routing|",
            f"|*Total*|{self.stats['queues']['total']:,}| |",
            "",
            "h2. 5.3 Data Ownership",
            "",
        ]

        # Show top applications by queue count
        sorted_apps = sorted(
            self.capabilities['by_application'].items(),
            key=lambda x: x[1]['total_queues'],
            reverse=True
        )[:10]

        ownership_table = ["||Data Domain||Owner||Primary Application(s)||"]
        for app_name, app_info in sorted_apps:
            ownership_table.append(f"|{app_info['dept']}|{app_info['biz_ownr']}|{app_name}|")

        lines.extend(self._expandable("Top 10 Data Owners by Queue Count", ownership_table))

        lines.extend(["", "----", ""])
        return lines

    def _generate_application_architecture(self) -> List[str]:
        """Generate Application Architecture section."""
        lines = [
            "{anchor:application-architecture}",
            "h1. 6. Application Architecture (Information Systems)",
            "",
            "h2. 6.1 Application Portfolio",
            "",
            "{info}",
            f"The MQ infrastructure supports {len(self.stats['applications'])} applications across {len(self.stats['departments'])} departments.",
            "{info}",
            "",
            "h3. Top Applications by Integration Complexity",
            "",
        ]

        sorted_apps = sorted(
            self.capabilities['by_application'].items(),
            key=lambda x: x[1]['connections'],
            reverse=True
        )[:15]

        apps_table = ["||Application||Organization||Department||MQ Managers||Connections||Queues||"]
        for app_name, app_info in sorted_apps:
            apps_table.append(f"|{app_name}|{app_info['org']}|{app_info['dept']}|{len(app_info['mqmanagers'])}|{app_info['connections']}|{app_info['total_queues']}|")

        lines.extend(self._expandable("Top 15 Applications by Integration Complexity", apps_table))

        lines.extend([
            "",
            "h2. 6.2 Application Dependencies",
            "",
        ])

        if self.dependencies['app_to_app']:
            dep_table = ["||Source Application||Depends On||"]
            for source_app, target_apps in sorted(self.dependencies['app_to_app'].items())[:20]:
                if not source_app.startswith('Gateway ('):
                    target_list = ', '.join([t for t in sorted(target_apps) if not t.startswith('Gateway (')])
                    if target_list:
                        dep_table.append(f"|{source_app}|{target_list}|")
            lines.extend(self._expandable("Application Dependencies", dep_table))
        else:
            lines.append("{tip}No direct application dependencies detected{tip}")

        lines.extend([
            "",
            "h2. 6.3 Cross-Organizational Dependencies",
            "",
        ])

        if self.dependencies['org_to_org']:
            lines.append("||Source Organization||Target Organizations||Dependency Count||")
            for source_org, target_orgs in sorted(self.dependencies['org_to_org'].items()):
                target_list = ', '.join(sorted(target_orgs))
                lines.append(f"|{source_org}|{target_list}|{len(target_orgs)}|")
        else:
            lines.append("{tip}No cross-organizational dependencies detected{tip}")

        lines.extend(["", "----", ""])
        return lines

    def _generate_technology_architecture(self) -> List[str]:
        """Generate Technology Architecture section."""
        internal_gateways = [g for g in self.stats['gateways'] if g['scope'] == 'Internal']
        external_gateways = [g for g in self.stats['gateways'] if g['scope'] == 'External']

        lines = [
            "{anchor:technology-architecture}",
            "h1. 7. Technology Architecture",
            "",
            "h2. 7.1 Technology Stack",
            "",
            "||Layer||Technology||Component Count||",
            f"|*Message Broker*|IBM MQ|{len(self.stats['mqmanagers'])} Queue Managers|",
            f"|*Internal Gateways*|IBM MQ Gateway Pattern|{len(internal_gateways)} Gateways|",
            f"|*External Gateways*|IBM MQ Gateway Pattern|{len(external_gateways)} Gateways|",
            f"|*Message Storage*|IBM MQ Queues|{self.stats['queues']['total']:,} Queues|",
            "",
            "h2. 7.2 Gateway Infrastructure",
            "",
            "{warning:title=Critical Infrastructure}",
            "Gateways are critical integration points. Ensure redundancy and monitoring.",
            "{warning}",
            "",
            "h3. Internal Gateways",
            "",
        ]

        int_gw_table = ["||Gateway||Organization||Department||Scope||"]
        for gw in sorted(internal_gateways, key=lambda x: x['name']):
            int_gw_table.append(f"|{gw['name']}|{gw['org']}|{gw['dept']}|Inter-departmental|")
        if not internal_gateways:
            int_gw_table.append("|_No internal gateways configured_| | | |")

        lines.extend(self._expandable(f"Internal Gateways ({len(internal_gateways)})", int_gw_table))

        lines.extend([
            "",
            "h3. External Gateways",
            "",
        ])

        ext_gw_table = ["||Gateway||Organization||Department||Scope||"]
        for gw in sorted(external_gateways, key=lambda x: x['name']):
            ext_gw_table.append(f"|{gw['name']}|{gw['org']}|{gw['dept']}|External Partners|")
        if not external_gateways:
            ext_gw_table.append("|_No external gateways configured_| | | |")

        lines.extend(self._expandable(f"External Gateways ({len(external_gateways)})", ext_gw_table))

        lines.extend([
            "",
            "h2. 7.3 Infrastructure Distribution",
            "",
            "||Organization||Type||MQ Managers||Gateways||",
        ])

        for org_name, org_info in sorted(self.stats['organizations'].items()):
            org_gateways = len([g for g in self.stats['gateways'] if g['org'] == org_name])
            type_badge = self._status_lozenge("Internal", "Green") if org_info['type'] == 'Internal' else self._status_lozenge("External", "Blue")
            lines.append(f"|{org_name}|{type_badge}|{org_info['mqmanagers']}|{org_gateways}|")

        lines.extend(["", "----", ""])
        return lines

    def _generate_integration_patterns(self) -> List[str]:
        """Generate Integration Patterns section."""
        total_patterns = self.integration_patterns['gateway_mediated'] + self.integration_patterns['direct_integration']
        gw_percent = round(100 * self.integration_patterns['gateway_mediated'] / max(1, total_patterns))

        lines = [
            "{anchor:integration-patterns}",
            "h1. 8. Integration Patterns & Standards",
            "",
            "h2. 8.1 Pattern Analysis",
            "",
            "||Pattern||Count||Percentage||Assessment||",
            f"|*Gateway-Mediated*|{self.integration_patterns['gateway_mediated']}|{gw_percent}%|{self._status_lozenge('Best Practice', 'Green')}|",
            f"|*Direct Point-to-Point*|{self.integration_patterns['direct_integration']}|{100-gw_percent}%|{self._status_lozenge('Monitor', 'Yellow')}|",
            "",
        ]

        if self.integration_patterns['hub_and_spoke']:
            lines.extend([
                "h2. 8.2 Hub-and-Spoke Patterns",
                "",
                "{info}",
                "Hub-and-spoke patterns indicate centralized integration points with high connection counts.",
                "{info}",
                "",
            ])
            hub_table = ["||Gateway||Scope||Connections||Risk Level||"]
            for hub in sorted(self.integration_patterns['hub_and_spoke'], key=lambda x: x['connections'], reverse=True):
                risk = self._status_lozenge("High", "Red") if hub['connections'] > 20 else self._status_lozenge("Medium", "Yellow")
                hub_table.append(f"|{hub['gateway']}|{hub['scope']}|{hub['connections']}|{risk}|")
            lines.extend(self._expandable("Hub-and-Spoke Gateways", hub_table))
            lines.append("")

        if self.integration_patterns['high_fanout']:
            lines.extend([
                "h2. 8.3 High Fan-Out Components",
                "",
            ])
            fanout_table = ["||MQ Manager||Outbound Connections||Recommendation||"]
            for item in sorted(self.integration_patterns['high_fanout'], key=lambda x: x['count'], reverse=True):
                fanout_table.append(f"|{item['mqmgr']}|{item['count']}|Review for potential mediation|")
            lines.extend(self._expandable("High Fan-Out Components", fanout_table))
            lines.append("")

        lines.extend([
            "h2. 8.4 Integration Standards",
            "",
            "||Standard||Description||Compliance||",
            "|*Naming Convention*|{{ORG}}_{{DEPT}}_{{APP}}_MQ##|Review Required|",
            "|*Queue Naming*|{{APP}}.{{FUNCTION}}.{{TYPE}}|Review Required|",
            "|*Security*|TLS 1.2+ for channels|Audit Required|",
            "|*Monitoring*|All queue managers monitored|Review Required|",
            "",
            "----",
            ""
        ])
        return lines

    def _generate_gap_analysis(self) -> List[str]:
        """Generate Gap Analysis section."""
        lines = [
            "{anchor:gap-analysis}",
            "h1. 9. Gap Analysis & Opportunities",
            "",
            "h2. 9.1 Architecture Maturity Assessment",
            "",
            f"*Overall Maturity Level:* {self.maturity['overall_level']}/5",
            "",
            "||Dimension||Score||Target||Gap||",
        ]

        for dimension, score in self.maturity['dimensions'].items():
            dimension_name = dimension.replace('_', ' ').title()
            gap = 5 - score
            gap_lozenge_colour = "Green" if gap <= 1 else ("Yellow" if gap <= 2 else "Red")
            lines.append(f"|{dimension_name}|{score}/5|5/5|{self._status_lozenge(f'Gap: {gap}', gap_lozenge_colour)}|")

        lines.extend([
            "",
            "h2. 9.2 Identified Gaps",
            "",
        ])

        if self.maturity['recommendations']:
            for i, rec in enumerate(self.maturity['recommendations'], 1):
                lines.append(f"# {rec}")
        else:
            lines.append("{tip}No significant gaps identified{tip}")

        lines.extend([
            "",
            "h2. 9.3 Improvement Opportunities",
            "",
            "||Opportunity||Impact||Effort||Priority||",
            f"|Implement gateway redundancy|High|Medium|{self._status_lozenge('P1', 'Red')}|",
            f"|Standardize naming conventions|Medium|Low|{self._status_lozenge('P2', 'Yellow')}|",
            f"|Consolidate high-complexity integrations|Medium|High|{self._status_lozenge('P2', 'Yellow')}|",
            f"|Implement centralized monitoring|High|Medium|{self._status_lozenge('P1', 'Red')}|",
            f"|Document message formats/schemas|Medium|Medium|{self._status_lozenge('P3', 'Blue')}|",
            "",
            "----",
            ""
        ])
        return lines

    def _generate_risk_assessment(self) -> List[str]:
        """Generate Risk Assessment section following RAID."""
        lines = [
            "{anchor:risk-assessment}",
            "h1. 10. Risk Assessment (RAID Log)",
            "",
            "{note:title=RAID Framework}",
            "Risks, Assumptions, Issues, and Dependencies affecting the architecture.",
            "{note}",
            "",
            "h2. 10.1 Critical Risks",
            "",
        ]

        if self.risks['critical']:
            lines.append("||ID||Category||Description||Impact||Mitigation||")
            for risk in self.risks['critical']:
                lines.append(f"|{self._status_lozenge(risk['id'], 'Red')}|{risk['category']}|{risk['description']}|{risk['impact']}|{risk['mitigation']}|")
        else:
            lines.append("{tip}No critical risks identified{tip}")

        lines.extend(["", "h2. 10.2 High Risks", ""])

        if self.risks['high']:
            lines.append("||ID||Category||Description||Impact||Mitigation||")
            for risk in self.risks['high']:
                lines.append(f"|{self._status_lozenge(risk['id'], 'Yellow')}|{risk['category']}|{risk['description']}|{risk['impact']}|{risk['mitigation']}|")
        else:
            lines.append("{tip}No high risks identified{tip}")

        lines.extend(["", "h2. 10.3 Medium Risks", ""])

        if self.risks['medium']:
            med_table = ["||ID||Category||Description||Mitigation||"]
            for risk in self.risks['medium'][:5]:
                med_table.append(f"|{self._status_lozenge(risk['id'], 'Grey')}|{risk['category']}|{risk['description']}|{risk['mitigation']}|")
            lines.extend(self._expandable(f"Medium Risks ({len(self.risks['medium'])})", med_table))
        else:
            lines.append("{tip}No medium risks identified{tip}")

        lines.extend(["", "h2. 10.4 Assumptions", ""])

        assumption_table = ["||ID||Assumption||Owner||Validation Date||"]
        for assumption in self.risks['assumptions']:
            assumption_table.append(f"|{assumption['id']}|{assumption['description']}|{assumption['owner']}|{assumption['validation_date']}|")
        lines.extend(self._expandable("Assumptions", assumption_table))

        lines.extend(["", "h2. 10.5 Dependencies", ""])

        if self.risks['dependencies']:
            dep_table = ["||ID||Description||Owner||Status||"]
            for dep in self.risks['dependencies']:
                dep_table.append(f"|{dep['id']}|{dep['description']}|{dep['owner']}|{dep['status']}|")
            lines.extend(self._expandable("Dependencies", dep_table))
        else:
            lines.append("{tip}No external dependencies documented{tip}")

        lines.extend(["", "----", ""])
        return lines

    def _generate_roadmap(self) -> List[str]:
        """Generate Architecture Roadmap section."""
        return [
            "{anchor:architecture-roadmap}",
            "h1. 11. Architecture Roadmap",
            "",
            "h2. 11.1 Recommended Initiatives",
            "",
            *self._styled_panel("Short-Term (0-6 months)", [
                "# *Gateway Redundancy* - Implement redundant gateways for organizations with SPOF",
                "# *Documentation* - Complete queue naming standards documentation",
                "# *Monitoring* - Deploy centralized MQ monitoring solution",
            ], bg_color="#e8f5e9", title_bg="#2e7d32", title_color="#fff", border_color="#a5d6a7"),
            "",
            *self._styled_panel("Medium-Term (6-12 months)", [
                "# *Pattern Consolidation* - Migrate point-to-point integrations to gateway pattern",
                "# *Security Hardening* - Implement TLS 1.3 for all channels",
                "# *Capacity Planning* - Establish baseline metrics and growth projections",
            ], bg_color="#fff3e0", title_bg="#e65100", title_color="#fff", border_color="#ffcc80"),
            "",
            *self._styled_panel("Long-Term (12-24 months)", [
                "# *Modernization* - Evaluate cloud-native messaging alternatives",
                "# *Automation* - Implement infrastructure-as-code for MQ provisioning",
                "# *Self-Service* - Enable application teams to manage their own queues",
            ], bg_color="#e3f2fd", title_bg="#1565c0", title_color="#fff", border_color="#90caf9"),
            "",
            "h2. 11.2 Success Metrics",
            "",
            "||Metric||Current||Target||Timeline||",
            f"|Gateway Redundancy|{len([g for g in self.stats['gateways']])} total|100% redundant|{self._status_lozenge('6 months', 'Red')}|",
            f"|Gateway-Mediated %|{round(100 * self.integration_patterns['gateway_mediated'] / max(1, self.integration_patterns['gateway_mediated'] + self.integration_patterns['direct_integration']))}%|>80%|{self._status_lozenge('12 months', 'Yellow')}|",
            f"|MTTR for incidents|Unknown|<1 hour|{self._status_lozenge('6 months', 'Red')}|",
            f"|Documentation coverage|Partial|100%|{self._status_lozenge('3 months', 'Green')}|",
            "",
            "----",
            ""
        ]

    def _generate_appendices(self) -> List[str]:
        """Generate Appendices section."""
        return [
            "{anchor:appendices}",
            "h1. 12. Appendices",
            "",
            "h2. 12.1 Generated Artifacts",
            "",
            "||Artifact||Description||Location||",
            "|Hierarchical Topology Diagram|Full topology visualization|mq_topology.pdf|",
            "|Application Diagrams|Per-application integration views|application_diagrams/|",
            "|Individual MQ Manager Diagrams|Detailed MQ manager views|individual_diagrams/|",
            "|Gateway Analytics Report|Gateway performance analysis|gateway_analytics_*.html|",
            "|Change Detection Report|Topology change tracking|change_report_*.html|",
            "|Excel Inventory|Complete MQ inventory export|mqcmdb_inventory_*.xlsx|",
            "",
            "h2. 12.2 Glossary",
            "",
            *self._expandable("Glossary", [
                "||Term||Definition||",
                "|*MQ Manager*|IBM MQ Queue Manager - the runtime component that hosts queues|",
                "|*QLOCAL*|Local Queue - stores messages on the queue manager|",
                "|*QREMOTE*|Remote Queue - definition pointing to a queue on another manager|",
                "|*QALIAS*|Alias Queue - provides an alternative name for another queue|",
                "|*Gateway*|MQ Manager designated for cross-boundary integration|",
                "|*SPOF*|Single Point of Failure - component without redundancy|",
                "|*Fan-Out*|Pattern where one source sends to many destinations|",
                "|*Fan-In*|Pattern where many sources send to one destination|",
            ]),
            "",
            "h2. 12.3 References",
            "",
            *self._expandable("References", [
                "* [TOGAF 9.2 Standard|https://pubs.opengroup.org/architecture/togaf9-doc/arch/]",
                "* [IBM MQ Documentation|https://www.ibm.com/docs/en/ibm-mq]",
                "* [Integration Patterns|https://www.enterpriseintegrationpatterns.com/]",
            ]),
            ""
        ]

    def _generate_footer(self) -> List[str]:
        """Generate document footer."""
        footer_content = [
            f"_This TOGAF-aligned Enterprise Architecture documentation was automatically generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
            "_by MQ CMDB Hierarchical Automation System_",
            "",
            f"*Document Version:* 1.0 | *Framework:* TOGAF 9.2 | *Classification:* {self._status_lozenge('Internal', 'Blue')} | {self._status_lozenge('AUTO-GENERATED', 'Grey')}",
        ]
        return [
            "----",
            *self._styled_panel(
                "Document Information",
                footer_content,
                bg_color="#f0f0f0",
                title_bg="#2d3e50",
                title_color="#ffffff",
                border_color="#c1c7d0",
            ),
        ]
