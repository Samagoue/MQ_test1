"""
Mashup processor to enrich MQ data with organizational hierarchy and application info.
"""

import json
from pathlib import Path
from typing import Dict, List

class HierarchyMashup:
    """Enrich MQ data with organizational hierarchy and application information."""

    def __init__(self, org_hierarchy_file: Path, app_to_qmgr_file: Path, gateways_file: Path = None):
        self.org_hierarchy = self._load_org_hierarchy(org_hierarchy_file)
        self.app_mapping = self._load_app_mapping(app_to_qmgr_file)
        self.gateway_mapping = self._load_gateway_mapping(gateways_file)
        print(f"✓ Loaded {len(self.org_hierarchy)} business owners from hierarchy")
        print(f"✓ Loaded {len(self.app_mapping)} application mappings")
        print(f"✓ Loaded {len(self.gateway_mapping)} gateway mappings")
   
    def _load_org_hierarchy(self, filepath: Path) -> Dict:
        """Load and index org hierarchy by Biz_Ownr (directorate)."""
        from utils.file_io import load_json
       
        if not filepath.exists():
            print(f"⚠ Warning: {filepath} not found. Using default hierarchy.")
            return {}
       
        data = load_json(filepath)
        hierarchy = {}
       
        for record in data:
            biz_ownr = str(record.get('Biz_Ownr', '')).strip()
            if biz_ownr:
                hierarchy[biz_ownr] = {
                    'Organization': str(record.get('Organization', 'Unknown')).strip(),
                    'Department': str(record.get('Department', 'Unknown')).strip(),
                    'Biz_Ownr': biz_ownr,
                    'Org_Type': str(record.get('Org_Type', 'Internal')).strip()
                }
       
        return hierarchy
   
    def _load_app_mapping(self, filepath: Path) -> Dict:
        """Load and index application mapping by QmgrName."""
        from utils.file_io import load_json

        if not filepath.exists():
            print(f"⚠ Warning: {filepath} not found. Using default app mappings.")
            return {}

        data = load_json(filepath)
        mapping = {}

        for record in data:
            qmgr_name = str(record.get('QmgrName', '')).strip()
            if qmgr_name:
                mapping[qmgr_name] = str(record.get('Application', 'No Application')).strip()

        return mapping

    def _load_gateway_mapping(self, filepath: Path) -> Dict:
        """Load and index gateway mapping by QmgrName."""
        from utils.file_io import load_json

        if filepath is None or not filepath.exists():
            if filepath is not None:
                print(f"⚠ Warning: {filepath} not found. No gateway mappings loaded.")
            return {}

        data = load_json(filepath)
        mapping = {}

        for record in data:
            qmgr_name = str(record.get('QmgrName', '')).strip()
            scope = str(record.get('Scope', 'Internal')).strip()
            if qmgr_name:
                mapping[qmgr_name] = {
                    'Scope': scope,
                    'Description': str(record.get('Description', '')).strip()
                }

        return mapping
   
    def enrich_data(self, processed_data: Dict) -> Dict:
        """
        Enrich processed MQ data with hierarchy and application info.
       
        Input: {directorate: {mqmanager: {...}}}
        Output: {Organization: {Department: {Biz_Ownr: {Application: {MQmanager: {...}}}}}}
        """
        enriched = {}
       
        for directorate, mqmanagers in processed_data.items():
            # Get hierarchy info for this directorate (Biz_Ownr)
            hierarchy_info = self.org_hierarchy.get(directorate, {
                'Organization': 'Unknown Organization',
                'Department': 'Unknown Department',
                'Biz_Ownr': directorate,
                'Org_Type': 'Internal'
            })
           
            org = hierarchy_info['Organization']
            dept = hierarchy_info['Department']
            biz_ownr = hierarchy_info['Biz_Ownr']
            org_type = hierarchy_info['Org_Type']
           
            # Initialize hierarchy levels
            if org not in enriched:
                enriched[org] = {'_org_type': org_type, '_departments': {}}
            if dept not in enriched[org]['_departments']:
                enriched[org]['_departments'][dept] = {}
            if biz_ownr not in enriched[org]['_departments'][dept]:
                enriched[org]['_departments'][dept][biz_ownr] = {}
           
            # Process each MQ manager
            for mqmanager, mq_data in mqmanagers.items():
                # Check if this MQ manager is a gateway
                gateway_info = self.gateway_mapping.get(mqmanager)

                if gateway_info:
                    # This is a gateway - use Gateway cluster instead of Application
                    gateway_scope = gateway_info['Scope']
                    gateway_name = f"Gateway ({gateway_scope})"

                    if gateway_name not in enriched[org]['_departments'][dept][biz_ownr]:
                        enriched[org]['_departments'][dept][biz_ownr][gateway_name] = {}

                    # Add enriched gateway MQ manager data
                    enriched[org]['_departments'][dept][biz_ownr][gateway_name][mqmanager] = {
                        'Organization': org,
                        'Org_Type': org_type,
                        'Department': dept,
                        'Biz_Ownr': biz_ownr,
                        'Application': gateway_name,
                        'MQmanager': mqmanager,
                        'qlocal_count': mq_data.get('qlocal_count', 0),
                        'qremote_count': mq_data.get('qremote_count', 0),
                        'qalias_count': mq_data.get('qalias_count', 0),
                        'total_count': mq_data.get('total_count', 0),
                        'inbound': mq_data.get('inbound', []),
                        'outbound': mq_data.get('outbound', []),
                        'inbound_extra': mq_data.get('inbound_extra', []),
                        'outbound_extra': mq_data.get('outbound_extra', []),
                        'IsGateway': True,
                        'GatewayScope': gateway_scope,
                        'GatewayDescription': gateway_info.get('Description', '')
                    }
                else:
                    # Regular application MQ manager
                    application = self.app_mapping.get(mqmanager, 'No Application')

                    if application not in enriched[org]['_departments'][dept][biz_ownr]:
                        enriched[org]['_departments'][dept][biz_ownr][application] = {}

                    # Add enriched MQ manager data
                    enriched[org]['_departments'][dept][biz_ownr][application][mqmanager] = {
                        'Organization': org,
                        'Org_Type': org_type,
                        'Department': dept,
                        'Biz_Ownr': biz_ownr,
                        'Application': application,
                        'MQmanager': mqmanager,
                        'qlocal_count': mq_data.get('qlocal_count', 0),
                        'qremote_count': mq_data.get('qremote_count', 0),
                        'qalias_count': mq_data.get('qalias_count', 0),
                        'total_count': mq_data.get('total_count', 0),
                        'inbound': mq_data.get('inbound', []),
                        'outbound': mq_data.get('outbound', []),
                        'inbound_extra': mq_data.get('inbound_extra', []),
                        'outbound_extra': mq_data.get('outbound_extra', []),
                        'IsGateway': False
                    }
       
        return enriched
