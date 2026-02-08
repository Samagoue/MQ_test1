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
from utils.logging_config import get_logger
from utils.parallel import DiagramTask, run_parallel

logger = get_logger("smart_filter")


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
                        # Check for exact scope match: "Gateway (Internal)" or "Gateway (External)"
                        if scope and app_name != f'Gateway ({scope})':
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


def _generate_single_filtered(label: str, filtered_data: Dict, dot_file: Path, Config):
    """Generate a single filtered diagram (DOT + PDF)."""
    from generators.graphviz_hierarchical import HierarchicalGraphVizGenerator

    gen = HierarchicalGraphVizGenerator(filtered_data, Config)
    gen.save_to_file(dot_file)

    pdf_file = dot_file.with_suffix('.pdf')
    gen.generate_pdf(dot_file, pdf_file)


def generate_filtered_diagrams(enriched_data: Dict, output_dir: Path, Config, max_workers: int = None):
    """
    Generate all filtered diagram views automatically.

    Args:
        enriched_data: Full enriched MQ CMDB data
        output_dir: Directory for filtered diagrams
        Config: Configuration object
        max_workers: Number of parallel workers (None = default)
    """
    output_dir.mkdir(exist_ok=True)
    tasks = []

    # 1. Per-Organization Diagrams
    for org_name in enriched_data.keys():
        org_data = filter_by_organization(enriched_data, org_name)
        if org_data:
            sanitized_name = org_name.replace(' ', '_').replace('/', '_')
            dot_file = output_dir / f"org_{sanitized_name}.dot"
            tasks.append(DiagramTask(
                f"filtered:org_{sanitized_name}",
                _generate_single_filtered,
                f"org_{sanitized_name}", org_data, dot_file, Config
            ))

    # 2. Gateways-Only Diagram
    gateway_data = filter_gateways_only(enriched_data)
    if gateway_data:
        tasks.append(DiagramTask(
            "filtered:gateways_only",
            _generate_single_filtered,
            "gateways_only", gateway_data, output_dir / "gateways_only.dot", Config
        ))

    # 3. Internal Gateways Only
    internal_gw_data = filter_gateways_only(enriched_data, scope='Internal')
    if internal_gw_data:
        tasks.append(DiagramTask(
            "filtered:gateways_internal",
            _generate_single_filtered,
            "gateways_internal", internal_gw_data, output_dir / "gateways_internal.dot", Config
        ))

    # 4. External Gateways Only
    external_gw_data = filter_gateways_only(enriched_data, scope='External')
    if external_gw_data:
        tasks.append(DiagramTask(
            "filtered:gateways_external",
            _generate_single_filtered,
            "gateways_external", external_gw_data, output_dir / "gateways_external.dot", Config
        ))

    if not tasks:
        return 0

    result = run_parallel(tasks, max_workers=max_workers)
    return result.success_count
