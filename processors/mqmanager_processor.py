
"""
MQ Manager Processor

Parses CMDB asset records to build the directorate-level MQ topology.
Each record contains an MQ manager name, an asset string, and a Role
(SENDER/RECEIVER). The processor extracts connection pairs by matching
known MQ manager names inside asset strings and tracks queue counts
(QLocal, QRemote, QAlias) per manager.
"""

from typing import Dict, List, Optional
from collections import defaultdict
from utils.logging_config import get_logger

logger = get_logger("processors.mqmanager")


class MQManagerProcessor:
    """Process MQ CMDB assets using the original working logic."""
 
    def __init__(self, raw_data: List[Dict], field_mappings: Dict[str, str]):
        """Initialize processor with raw data and field mappings."""
        if not isinstance(raw_data, list):
            raise ValueError(f"Input data must be a list, got {type(raw_data)}")
     
        if len(raw_data) == 0:
            raise ValueError("Input data list is empty")
     
        self.raw_data = raw_data
        self.field_mappings = field_mappings
     
        # Collections for processing
        self.valid_mqmanagers = set()
        self.mqmanager_to_directorate = {}
        self.canonical_mqmanagers = {}  # UPPER -> canonical name from raw data
     
        self.stats = {
            'total_records': len(self.raw_data),
            'processed_sender': 0,
            'processed_receiver': 0,
            'inbound_found': 0,
            'outbound_found': 0,
            'inbound_extra_found': 0,
            'outbound_extra_found': 0
        }
     
        logger.info(f"✓ Initialized with {len(self.raw_data)} records")
 
    def _normalize_value(self, val) -> str:
        """Normalize string values."""
        if val is None:
            return ""
        return str(val).strip()
 
    def _extract_mqmanager_from_asset(self, asset: str, mqmanager: str) -> str:
        """
        Extract the remaining string after removing MQmanager prefix from asset.
        Removes leading/trailing dots.
        """
        asset = self._normalize_value(asset)
        mqmanager = self._normalize_value(mqmanager)
     
        if not asset or not mqmanager:
            return ""
     
        asset_upper = asset.upper()
        mqmanager_upper = mqmanager.upper()
     
        # Remove MQmanager prefix
        prefix = mqmanager_upper + "."
        if asset_upper.startswith(prefix):
            remaining = asset[len(prefix):]
        elif mqmanager_upper in asset_upper:
            idx = asset_upper.find(mqmanager_upper)
            remaining = asset[idx + len(mqmanager):]
            if remaining.startswith('.'):
                remaining = remaining[1:]
        else:
            remaining = asset
     
        # Remove leading and trailing dots
        remaining = remaining.strip('.')
     
        return remaining
 
    def _find_mqmanager_in_string(self, text: str, exclude_mqmanager: str = "") -> Optional[str]:
        """
        Check if any valid MQmanager name exists in the text.
        Returns the canonical MQmanager name if found, None otherwise.
        """
        if not text:
            return None

        text_upper = text.upper()
        exclude_upper = exclude_mqmanager.upper()

        # Split by dots and check each part
        parts = text.split('.')
        for part in parts:
            part_upper = part.upper()
            if part_upper in self.valid_mqmanagers and part_upper != exclude_upper:
                return self.canonical_mqmanagers.get(part_upper, part)

        # Check if entire string matches
        if text_upper in self.valid_mqmanagers and text_upper != exclude_upper:
            return self.canonical_mqmanagers.get(text_upper, text)

        return None
 
    def _build_index(self):
        """First pass: collect all valid MQmanager names."""
        logger.info("Building MQ Manager index...")
     
        for record in self.raw_data:
            if not isinstance(record, dict):
                continue
         
            mqmanager_field = self.field_mappings.get('mqmanager', 'MQmanager')
            directorate_field = self.field_mappings.get('directorate', 'directorate')
         
            mqmanager = self._normalize_value(record.get(mqmanager_field, ''))
         
            if mqmanager:
                mqmanager_upper = mqmanager.upper()
                self.valid_mqmanagers.add(mqmanager_upper)
                # Store canonical name (first occurrence wins)
                if mqmanager_upper not in self.canonical_mqmanagers:
                    self.canonical_mqmanagers[mqmanager_upper] = mqmanager
                directorate = self._normalize_value(record.get(directorate_field, ''))
                if not directorate:
                    directorate = "Unknown"
                # Store with uppercase key for consistent lookups
                self.mqmanager_to_directorate[mqmanager_upper] = directorate
     
        logger.info(f"✓ Found {len(self.valid_mqmanagers)} unique MQ Managers")
 
    def process_assets(self) -> Dict:
        """
        Process all assets and extract relationships - ORIGINAL WORKING LOGIC.
        Returns: {directorate: {mqmanager: {...}}}
        """
        logger.info("Processing MQ CMDB assets...")
     
        # Build index first
        self._build_index()
     
        # Structure to hold processed data
        directorate_data = defaultdict(lambda: defaultdict(lambda: {
            'qlocal_count': 0,
            'qremote_count': 0,
            'qalias_count': 0,
            'total_count': 0,
            'inbound': set(),
            'outbound': set(),
            'inbound_extra': set(),
            'outbound_extra': set()
        }))
     
        # Get field names
        mqmanager_field = self.field_mappings.get('mqmanager', 'MQmanager')
        asset_field = self.field_mappings.get('asset', 'asset')
        asset_type_field = self.field_mappings.get('asset_type', 'asset_type')
        directorate_field = self.field_mappings.get('directorate', 'directorate')
        role_field = self.field_mappings.get('role', 'Role')
     
        # Second pass: process each record
        for record in self.raw_data:
            if not isinstance(record, dict):
                continue
         
            mqmanager = self._normalize_value(record.get(mqmanager_field, ''))
            asset = self._normalize_value(record.get(asset_field, ''))
            asset_type = self._normalize_value(record.get(asset_type_field, '')).lower()
            directorate = self._normalize_value(record.get(directorate_field, ''))
            role = self._normalize_value(record.get(role_field, '')).upper()
         
            if not mqmanager:
                continue
         
            # Use "Unknown" if directorate is empty
            if not directorate:
                directorate = "Unknown"
         
            # Count assets by type
            if 'local' in asset_type and 'remote' not in asset_type:
                directorate_data[directorate][mqmanager]['qlocal_count'] += 1
                directorate_data[directorate][mqmanager]['total_count'] += 1
            elif 'remote' in asset_type:
                directorate_data[directorate][mqmanager]['qremote_count'] += 1
                directorate_data[directorate][mqmanager]['total_count'] += 1
            elif 'alias' in asset_type:
                directorate_data[directorate][mqmanager]['qalias_count'] += 1
                directorate_data[directorate][mqmanager]['total_count'] += 1
         
            # Process Sender/Receiver logic with bidirectional tracking
            # SENDER means: this MQmanager SENDS to the target (outbound connection)
            # RECEIVER means: this MQmanager RECEIVES from the source (inbound connection)
         
            if 'SENDER' in role and asset:
                self.stats['processed_sender'] += 1
             
                # Extract remaining string after removing MQmanager
                remaining = self._extract_mqmanager_from_asset(asset, mqmanager)
             
                if remaining:
                    # Check if remaining contains another MQmanager
                    found_mqmanager = self._find_mqmanager_in_string(remaining, mqmanager)
                 
                    if found_mqmanager:
                        # This MQmanager sends TO found_mqmanager -> Outbound
                        directorate_data[directorate][mqmanager]['outbound'].add(found_mqmanager)
                        self.stats['outbound_found'] += 1
                     
                        # INVERSE: found_mqmanager receives FROM this mqmanager
                        # Use uppercase for lookup to match how keys are stored
                        target_dir = self.mqmanager_to_directorate.get(found_mqmanager.upper(), "Unknown")
                        directorate_data[target_dir][found_mqmanager]['inbound'].add(mqmanager)
                    else:
                        # No MQmanager found -> Outbound_Extra
                        directorate_data[directorate][mqmanager]['outbound_extra'].add(remaining)
                        self.stats['outbound_extra_found'] += 1

            elif 'RECEIVER' in role and asset:
                self.stats['processed_receiver'] += 1

                # Extract remaining string after removing MQmanager
                remaining = self._extract_mqmanager_from_asset(asset, mqmanager)

                if remaining:
                    # Check if remaining contains another MQmanager
                    found_mqmanager = self._find_mqmanager_in_string(remaining, mqmanager)

                    if found_mqmanager:
                        # This MQmanager receives FROM found_mqmanager -> Inbound
                        directorate_data[directorate][mqmanager]['inbound'].add(found_mqmanager)
                        self.stats['inbound_found'] += 1

                        # INVERSE: found_mqmanager sends TO this mqmanager
                        # Use uppercase for lookup to match how keys are stored
                        target_dir = self.mqmanager_to_directorate.get(found_mqmanager.upper(), "Unknown")
                        directorate_data[target_dir][found_mqmanager]['outbound'].add(mqmanager)
                    else:
                        # No MQmanager found -> Inbound_Extra
                        directorate_data[directorate][mqmanager]['inbound_extra'].add(remaining)
                        self.stats['inbound_extra_found'] += 1
     
        return directorate_data
 
    def convert_to_json(self, directorate_data: Dict) -> Dict:
        """
        Convert the processed data to final JSON structure.
        Converts sets to sorted lists.
        """
        result = {}
     
        for directorate, mqmanagers in directorate_data.items():
            result[directorate] = {}
         
            for mqmanager, data in mqmanagers.items():
                result[directorate][mqmanager] = {
                    'directorate': directorate,
                    'mqmanager': mqmanager,
                    'qlocal_count': data['qlocal_count'],
                    'qremote_count': data['qremote_count'],
                    'qalias_count': data['qalias_count'],
                    'total_count': data['total_count'],
                    'inbound': sorted(list(data['inbound'])),
                    'outbound': sorted(list(data['outbound'])),
                    'inbound_extra': sorted(list(data['inbound_extra'])),
                    'outbound_extra': sorted(list(data['outbound_extra']))
                }
     
        return result
 
    def print_stats(self):
        """Log processing statistics."""
        logger.info("\n" + "=" * 70)
        logger.info("PROCESSING STATISTICS")
        logger.info("=" * 70)
        logger.info(f"Total records:        {self.stats['total_records']}")
        logger.info(f"Sender records:       {self.stats['processed_sender']}")
        logger.info(f"Receiver records:     {self.stats['processed_receiver']}")
        logger.info(f"Inbound connections:  {self.stats['inbound_found']}")
        logger.info(f"Outbound connections: {self.stats['outbound_found']}")
        logger.info(f"Inbound_Extra:        {self.stats['inbound_extra_found']}")
        logger.info(f"Outbound_Extra:       {self.stats['outbound_extra_found']}")
        logger.info("=" * 70)



