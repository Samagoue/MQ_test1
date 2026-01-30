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
"""

from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime
from collections import defaultdict


class EADocumentationGenerator:
    """Generate TOGAF-aligned Enterprise Architecture documentation for MQ CMDB topology."""

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

    def generate_confluence_markup(self, output_file: Path):
        """Generate comprehensive TOGAF-aligned Confluence documentation."""
        doc = []

        # Document Header
        doc.extend(self._generate_document_header())

        # Table of Contents
        doc.extend(self._generate_toc())

        # 1. Architecture Vision
        doc.extend(self._generate_architecture_vision())

        # 2. Stakeholder Analysis
        doc.extend(self._generate_stakeholder_analysis())

        # 3. Architecture Principles
        doc.extend(self._generate_architecture_principles())

        # 4. Business Architecture
        doc.extend(self._generate_business_architecture())

        # 5. Information Systems Architecture - Data
        doc.extend(self._generate_data_architecture())

        # 6. Information Systems Architecture - Application
        doc.extend(self._generate_application_architecture())

        # 7. Technology Architecture
        doc.extend(self._generate_technology_architecture())

        # 8. Integration Patterns & Standards
        doc.extend(self._generate_integration_patterns())

        # 9. Gap Analysis & Opportunities
        doc.extend(self._generate_gap_analysis())

        # 10. Risk Assessment (RAID)
        doc.extend(self._generate_risk_assessment())

        # 11. Architecture Roadmap
        doc.extend(self._generate_roadmap())

        # 12. Appendices
        doc.extend(self._generate_appendices())

        # Footer
        doc.extend(self._generate_footer())

        # Write file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(doc))

        print(f"✓ EA Documentation (TOGAF-aligned) generated: {output_file}")
        return True

    def _generate_document_header(self) -> List[str]:
        """Generate document control header."""
        return [
            "{panel:title=TOGAF Architecture Document|borderStyle=solid}",
            "h1. MQ Integration Architecture",
            "",
            "||Document Property||Value||",
            "|*Document Type*|Enterprise Architecture - Integration Domain|",
            f"|*Generated*|{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}|",
            "|*Framework*|TOGAF 9.2 Architecture Content Framework|",
            "|*Scope*|IBM MQ Middleware Integration Topology|",
            "|*Classification*|Internal Use Only|",
            "|*Status*|Current State Architecture|",
            "{panel}",
            "",
            "{toc}",
            "",
            "----",
            ""
        ]

    def _generate_toc(self) -> List[str]:
        """Generate navigation panel."""
        return [
            "{panel:title=Quick Navigation}",
            "* [1. Architecture Vision|#architecture-vision]",
            "* [2. Stakeholder Analysis|#stakeholder-analysis]",
            "* [3. Architecture Principles|#architecture-principles]",
            "* [4. Business Architecture|#business-architecture]",
            "* [5. Data Architecture|#data-architecture]",
            "* [6. Application Architecture|#application-architecture]",
            "* [7. Technology Architecture|#technology-architecture]",
            "* [8. Integration Patterns|#integration-patterns]",
            "* [9. Gap Analysis|#gap-analysis]",
            "* [10. Risk Assessment|#risk-assessment]",
            "* [11. Architecture Roadmap|#architecture-roadmap]",
            "* [12. Appendices|#appendices]",
            "{panel}",
            ""
        ]

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
            "||Metric||Value||Details||",
            f"|*Organizations*|{len(self.stats['organizations'])}|{internal_orgs} Internal, {external_orgs} External|",
            f"|*Applications*|{len(self.stats['applications'])}|Integrated via MQ|",
            f"|*MQ Managers*|{len(self.stats['mqmanagers'])}|{internal_gw + external_gw} Gateways|",
            f"|*Message Queues*|{self.stats['queues']['total']:,}|Local: {self.stats['queues']['qlocal']:,}, Remote: {self.stats['queues']['qremote']:,}, Alias: {self.stats['queues']['qalias']:,}|",
            f"|*Departments*|{len(self.stats['departments'])}|Across all organizations|",
            f"|*Business Owners*|{len(self.stats['biz_owners'])}|Application stakeholders|",
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
            "# *Reliability* - Ensure message delivery guarantees across all integration paths",
            "# *Scalability* - Support growing message volumes and new integrations",
            "# *Security* - Protect message content and control access to queues",
            "# *Maintainability* - Enable efficient operations and change management",
            "# *Visibility* - Provide clear documentation and monitoring capabilities",
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
            "||Business Owner||Department||Applications||MQ Managers||",
        ]

        # Group by business owner
        biz_owner_stats = defaultdict(lambda: {'dept': '', 'apps': set(), 'mqmgrs': 0})
        for mqmgr_name, info in self.stats['mqmanagers'].items():
            biz_ownr = info.get('biz_ownr', 'Unknown')
            biz_owner_stats[biz_ownr]['dept'] = info.get('dept', '')
            if info['app'] and not info['app'].startswith('Gateway ('):
                biz_owner_stats[biz_ownr]['apps'].add(info['app'])
            biz_owner_stats[biz_ownr]['mqmgrs'] += 1

        for biz_ownr, stats in sorted(biz_owner_stats.items()):
            if biz_ownr != 'Unknown':
                lines.append(f"|{biz_ownr}|{stats['dept']}|{len(stats['apps'])}|{stats['mqmgrs']}|")

        lines.extend(["", "----", ""])
        return lines

    def _generate_architecture_principles(self) -> List[str]:
        """Generate Architecture Principles section."""
        return [
            "{anchor:architecture-principles}",
            "h1. 3. Architecture Principles",
            "",
            "{note:title=TOGAF Reference}",
            "Architecture Principles define the underlying general rules and guidelines for the use and deployment of IT resources.",
            "{note}",
            "",
            "h2. 3.1 Integration Principles",
            "",
            "{panel:title=PRIN-01: Gateway-Mediated Integration}",
            "*Statement:* All cross-organizational and cross-departmental integrations SHOULD be mediated through designated gateway MQ managers.",
            "",
            "*Rationale:* Centralized integration points provide better control, monitoring, and security enforcement.",
            "",
            "*Implications:*",
            "* Gateway infrastructure must be highly available",
            "* All external connections must route through external gateways",
            "* Direct point-to-point connections should be reviewed for migration",
            "{panel}",
            "",
            "{panel:title=PRIN-02: Asynchronous Messaging}",
            "*Statement:* Message-based integrations SHALL use asynchronous, guaranteed delivery patterns.",
            "",
            "*Rationale:* Asynchronous messaging provides loose coupling, resilience, and temporal decoupling between systems.",
            "",
            "*Implications:*",
            "* Applications must handle message persistence",
            "* Dead letter queue handling must be implemented",
            "* Message ordering may require additional design consideration",
            "{panel}",
            "",
            "{panel:title=PRIN-03: Hierarchical Organization}",
            "*Statement:* MQ infrastructure SHALL be organized following the organizational hierarchy: Organization -> Department -> Business Owner -> Application.",
            "",
            "*Rationale:* Alignment with organizational structure enables clear ownership, governance, and change management.",
            "",
            "*Implications:*",
            "* Naming conventions must reflect hierarchy",
            "* Access controls align with organizational boundaries",
            "* Capacity planning follows departmental structures",
            "{panel}",
            "",
            "{panel:title=PRIN-04: Separation of Concerns}",
            "*Statement:* Internal and external integration gateways SHALL be separated.",
            "",
            "*Rationale:* Different security, compliance, and operational requirements apply to internal vs. external integrations.",
            "",
            "*Implications:*",
            "* Separate gateway infrastructure for internal/external",
            "* Different security policies per gateway type",
            "* External gateways require additional hardening",
            "{panel}",
            "",
            "----",
            ""
        ]

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
            org_type_label = "(Internal)" if org_info['type'] == 'Internal' else "(External)"
            lines.extend([
                f"h3. {org_name} {org_type_label}",
                "",
                "||Metric||Value||",
                f"|Departments|{len(org_info['departments'])}|",
                f"|Applications|{len(org_info['applications'])}|",
                f"|MQ Managers|{org_info['mqmanagers']}|",
                ""
            ])

        lines.extend([
            "h2. 4.3 Department Capability Matrix",
            "",
            "||Department||Applications||MQ Managers||Total Queues||",
        ])

        for dept, info in sorted(self.capabilities['by_department'].items()):
            lines.append(f"|{dept}|{len(info['apps'])}|{info['mqmanagers']}|{info['queues']:,}|")

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
            "||Data Domain||Owner||Primary Application(s)||",
        ]

        # Show top applications by queue count
        sorted_apps = sorted(
            self.capabilities['by_application'].items(),
            key=lambda x: x[1]['total_queues'],
            reverse=True
        )[:10]

        for app_name, app_info in sorted_apps:
            lines.append(f"|{app_info['dept']}|{app_info['biz_ownr']}|{app_name}|")

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
            "||Application||Organization||Department||MQ Managers||Connections||Queues||",
        ]

        sorted_apps = sorted(
            self.capabilities['by_application'].items(),
            key=lambda x: x[1]['connections'],
            reverse=True
        )[:15]

        for app_name, app_info in sorted_apps:
            lines.append(f"|{app_name}|{app_info['org']}|{app_info['dept']}|{len(app_info['mqmanagers'])}|{app_info['connections']}|{app_info['total_queues']}|")

        lines.extend([
            "",
            "h2. 6.2 Application Dependencies",
            "",
        ])

        if self.dependencies['app_to_app']:
            lines.append("||Source Application||Depends On||")
            for source_app, target_apps in sorted(self.dependencies['app_to_app'].items())[:20]:
                if not source_app.startswith('Gateway ('):
                    target_list = ', '.join([t for t in sorted(target_apps) if not t.startswith('Gateway (')])[:80]
                    if target_list:
                        lines.append(f"|{source_app}|{target_list}|")
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
            "||Gateway||Organization||Department||Scope||",
        ]

        for gw in sorted(internal_gateways, key=lambda x: x['name']):
            lines.append(f"|{gw['name']}|{gw['org']}|{gw['dept']}|Inter-departmental|")
        if not internal_gateways:
            lines.append("|_No internal gateways configured_| | | |")

        lines.extend([
            "",
            "h3. External Gateways",
            "",
            "||Gateway||Organization||Department||Scope||",
        ])

        for gw in sorted(external_gateways, key=lambda x: x['name']):
            lines.append(f"|{gw['name']}|{gw['org']}|{gw['dept']}|External Partners|")
        if not external_gateways:
            lines.append("|_No external gateways configured_| | | |")

        lines.extend([
            "",
            "h2. 7.3 Infrastructure Distribution",
            "",
            "||Organization||Type||MQ Managers||Gateways||",
        ])

        for org_name, org_info in sorted(self.stats['organizations'].items()):
            org_gateways = len([g for g in self.stats['gateways'] if g['org'] == org_name])
            type_badge = "{color:green}Internal{color}" if org_info['type'] == 'Internal' else "{color:purple}External{color}"
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
            f"|*Gateway-Mediated*|{self.integration_patterns['gateway_mediated']}|{gw_percent}%|{{color:green}}✓ Best Practice{{color}}|",
            f"|*Direct Point-to-Point*|{self.integration_patterns['direct_integration']}|{100-gw_percent}%|{{color:orange}}⚠ Monitor{{color}}|",
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
                "||Gateway||Scope||Connections||Risk Level||",
            ])
            for hub in sorted(self.integration_patterns['hub_and_spoke'], key=lambda x: x['connections'], reverse=True):
                risk = "{color:red}High{color}" if hub['connections'] > 20 else "{color:orange}Medium{color}"
                lines.append(f"|{hub['gateway']}|{hub['scope']}|{hub['connections']}|{risk}|")
            lines.append("")

        if self.integration_patterns['high_fanout']:
            lines.extend([
                "h2. 8.3 High Fan-Out Components",
                "",
                "||MQ Manager||Outbound Connections||Recommendation||",
            ])
            for item in sorted(self.integration_patterns['high_fanout'], key=lambda x: x['count'], reverse=True):
                lines.append(f"|{item['mqmgr']}|{item['count']}|Review for potential mediation|")
            lines.append("")

        lines.extend([
            "h2. 8.4 Integration Standards",
            "",
            "||Standard||Description||Compliance||",
            "|*Naming Convention*|\\{org\\}_\\{dept\\}_\\{app\\}_MQ##|Review Required|",
            "|*Queue Naming*|\\{app\\}.\\{function\\}.\\{type\\}|Review Required|",
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
            gap_color = "green" if gap <= 1 else ("orange" if gap <= 2 else "red")
            lines.append(f"|{dimension_name}|{score}/5|5/5|{{color:{gap_color}}}{gap}{{color}}|")

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
            "|Implement gateway redundancy|High|Medium|{color:red}P1{color}|",
            "|Standardize naming conventions|Medium|Low|{color:orange}P2{color}|",
            "|Consolidate high-complexity integrations|Medium|High|{color:orange}P2{color}|",
            "|Implement centralized monitoring|High|Medium|{color:red}P1{color}|",
            "|Document message formats/schemas|Medium|Medium|{color:blue}P3{color}|",
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
                lines.append(f"|{{color:red}}{risk['id']}{{color}}|{risk['category']}|{risk['description']}|{risk['impact']}|{risk['mitigation']}|")
        else:
            lines.append("{tip}No critical risks identified{tip}")

        lines.extend(["", "h2. 10.2 High Risks", ""])

        if self.risks['high']:
            lines.append("||ID||Category||Description||Impact||Mitigation||")
            for risk in self.risks['high']:
                lines.append(f"|{{color:orange}}{risk['id']}{{color}}|{risk['category']}|{risk['description']}|{risk['impact']}|{risk['mitigation']}|")
        else:
            lines.append("{tip}No high risks identified{tip}")

        lines.extend(["", "h2. 10.3 Medium Risks", ""])

        if self.risks['medium']:
            lines.append("||ID||Category||Description||Mitigation||")
            for risk in self.risks['medium'][:5]:  # Limit to top 5
                lines.append(f"|{risk['id']}|{risk['category']}|{risk['description']}|{risk['mitigation']}|")
        else:
            lines.append("{tip}No medium risks identified{tip}")

        lines.extend([
            "",
            "h2. 10.4 Assumptions",
            "",
            "||ID||Assumption||Owner||Validation Date||",
        ])

        for assumption in self.risks['assumptions']:
            lines.append(f"|{assumption['id']}|{assumption['description']}|{assumption['owner']}|{assumption['validation_date']}|")

        lines.extend([
            "",
            "h2. 10.5 Dependencies",
            "",
        ])

        if self.risks['dependencies']:
            lines.append("||ID||Description||Owner||Status||")
            for dep in self.risks['dependencies']:
                lines.append(f"|{dep['id']}|{dep['description']}|{dep['owner']}|{dep['status']}|")
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
            "{panel:title=Short-Term (0-6 months)|bgColor=#e8f5e9}",
            "# *Gateway Redundancy* - Implement redundant gateways for organizations with SPOF",
            "# *Documentation* - Complete queue naming standards documentation",
            "# *Monitoring* - Deploy centralized MQ monitoring solution",
            "{panel}",
            "",
            "{panel:title=Medium-Term (6-12 months)|bgColor=#fff3e0}",
            "# *Pattern Consolidation* - Migrate point-to-point integrations to gateway pattern",
            "# *Security Hardening* - Implement TLS 1.3 for all channels",
            "# *Capacity Planning* - Establish baseline metrics and growth projections",
            "{panel}",
            "",
            "{panel:title=Long-Term (12-24 months)|bgColor=#e3f2fd}",
            "# *Modernization* - Evaluate cloud-native messaging alternatives",
            "# *Automation* - Implement infrastructure-as-code for MQ provisioning",
            "# *Self-Service* - Enable application teams to manage their own queues",
            "{panel}",
            "",
            "h2. 11.2 Success Metrics",
            "",
            "||Metric||Current||Target||Timeline||",
            f"|Gateway Redundancy|{len([g for g in self.stats['gateways']])} total|100% redundant|6 months|",
            f"|Gateway-Mediated %|{round(100 * self.integration_patterns['gateway_mediated'] / max(1, self.integration_patterns['gateway_mediated'] + self.integration_patterns['direct_integration']))}%|>80%|12 months|",
            "|MTTR for incidents|Unknown|<1 hour|6 months|",
            "|Documentation coverage|Partial|100%|3 months|",
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
            "||Term||Definition||",
            "|*MQ Manager*|IBM MQ Queue Manager - the runtime component that hosts queues|",
            "|*QLOCAL*|Local Queue - stores messages on the queue manager|",
            "|*QREMOTE*|Remote Queue - definition pointing to a queue on another manager|",
            "|*QALIAS*|Alias Queue - provides an alternative name for another queue|",
            "|*Gateway*|MQ Manager designated for cross-boundary integration|",
            "|*SPOF*|Single Point of Failure - component without redundancy|",
            "|*Fan-Out*|Pattern where one source sends to many destinations|",
            "|*Fan-In*|Pattern where many sources send to one destination|",
            "",
            "h2. 12.3 References",
            "",
            "* [TOGAF 9.2 Standard|https://pubs.opengroup.org/architecture/togaf9-doc/arch/]",
            "* [IBM MQ Documentation|https://www.ibm.com/docs/en/ibm-mq]",
            "* [Integration Patterns|https://www.enterpriseintegrationpatterns.com/]",
            ""
        ]

    def _generate_footer(self) -> List[str]:
        """Generate document footer."""
        return [
            "----",
            "{panel:bgColor=#f0f0f0}",
            f"_This TOGAF-aligned Enterprise Architecture documentation was automatically generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
            "_by MQ CMDB Hierarchical Automation System_",
            "",
            "*Document Version:* 1.0 | *Framework:* TOGAF 9.2 | *Classification:* Internal",
            "{panel}"
        ]
