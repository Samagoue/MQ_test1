"""
Smart Filtering for MQ CMDB Data

Generates filtered diagrams automatically as part of the pipeline:
- Per-organization views
- Per-department views
- Gateways-only view
- High-complexity connections view
"""

from pathlib import Path
from typing import Dict
from copy import deepcopy


def filter_by_organization(enriched_data: Dict, org_name: str) -> Dict:
    """Filter to single organization."""
    if org_name not in enriched_data:
        return {}
    return {org_name: deepcopy(enriched_data[org_name])}


def filter_by_department(enriched_data: Dict, org_name: str, dept_name: str) -> Dict:
    """Filter to single department within an organization."""
    if org_name not in enriched_data:
        return {}

    org_data = enriched_data[org_name]
    if not isinstance(org_data, dict) or '_departments' not in org_data:
        return {}

    if dept_name not in org_data['_departments']:
        return {}

    return {
        org_name: {
            '_org_type': org_data.get('_org_type', 'Internal'),
            '_departments': {
                dept_name: deepcopy(org_data['_departments'][dept_name])
            }
        }
    }


def filter_gateways_only(enriched_data: Dict, scope: str = None) -> Dict:
    """Filter to show only gateways."""
    filtered = {}

    for org_name, org_data in enriched_data.items():
        if not isinstance(org_data, dict) or '_departments' not in org_data:
            continue

        for dept_name, dept_data in org_data['_departments'].items():
            for biz_ownr, applications in dept_data.items():
                for app_name, mqmgr_dict in applications.items():
                    if app_name.startswith('Gateway ('):
                        if scope and not app_name.startswith(f'Gateway ({scope})'):
                            continue

                        if org_name not in filtered:
                            filtered[org_name] = {
                                '_org_type': org_data.get('_org_type', 'Internal'),
                                '_departments': {}
                            }

                        if dept_name not in filtered[org_name]['_departments']:
                            filtered[org_name]['_departments'][dept_name] = {}

                        if biz_ownr not in filtered[org_name]['_departments'][dept_name]:
                            filtered[org_name]['_departments'][dept_name][biz_ownr] = {}

                        filtered[org_name]['_departments'][dept_name][biz_ownr][app_name] = deepcopy(mqmgr_dict)

    return filtered


def generate_filtered_diagrams(enriched_data: Dict, output_dir: Path, Config):
    """
    Generate all filtered diagram views automatically.

    Args:
        enriched_data: Full enriched MQ CMDB data
        output_dir: Directory for filtered diagrams
        Config: Configuration object
    """
    from generators.graphviz_hierarchical import HierarchicalGraphVizGenerator

    output_dir.mkdir(exist_ok=True)
    generated_count = 0

    # 1. Per-Organization Diagrams
    for org_name in enriched_data.keys():
        org_data = filter_by_organization(enriched_data, org_name)
        if org_data:
            sanitized_name = org_name.replace(' ', '_').replace('/', '_')
            dot_file = output_dir / f"org_{sanitized_name}.dot"

            gen = HierarchicalGraphVizGenerator(org_data, Config)
            gen.save_to_file(dot_file)

            pdf_file = dot_file.with_suffix('.pdf')
            if gen.generate_pdf(dot_file, pdf_file):
                generated_count += 1

    # 2. Gateways-Only Diagram
    gateway_data = filter_gateways_only(enriched_data)
    if gateway_data:
        dot_file = output_dir / "gateways_only.dot"
        gen = HierarchicalGraphVizGenerator(gateway_data, Config)
        gen.save_to_file(dot_file)

        pdf_file = dot_file.with_suffix('.pdf')
        if gen.generate_pdf(dot_file, pdf_file):
            generated_count += 1

    # 3. Internal Gateways Only
    internal_gw_data = filter_gateways_only(enriched_data, scope='Internal')
    if internal_gw_data:
        dot_file = output_dir / "gateways_internal.dot"
        gen = HierarchicalGraphVizGenerator(internal_gw_data, Config)
        gen.save_to_file(dot_file)

        pdf_file = dot_file.with_suffix('.pdf')
        if gen.generate_pdf(dot_file, pdf_file):
            generated_count += 1

    # 4. External Gateways Only
    external_gw_data = filter_gateways_only(enriched_data, scope='External')
    if external_gw_data:
        dot_file = output_dir / "gateways_external.dot"
        gen = HierarchicalGraphVizGenerator(external_gw_data, Config)
        gen.save_to_file(dot_file)

        pdf_file = dot_file.with_suffix('.pdf')
        if gen.generate_pdf(dot_file, pdf_file):
            generated_count += 1

    return generated_count
