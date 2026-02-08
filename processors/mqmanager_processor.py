"""
MQ Manager Processor - Based on ACTUAL Working Logic
Uses the original asset-based parsing that extracts MQ manager names from asset strings.

Supports:
- MQ Manager aliases (e.g., QM1 = XX_QM1)
- Application detection from asset names
- Internal vs External application classification
"""

from typing import Dict, List, Optional, Set
from collections import defaultdict
from pathlib import Path
import json
from utils.logging_config import get_logger

logger = get_logger("processor.mqmanager")


class MQManagerProcessor:
    """Process MQ CMDB assets using the original working logic."""

    def __init__(self, raw_data: List[Dict], field_mappings: Dict[str, str],
                 aliases_file: Optional[Path] = None,
                 app_to_qmgr_file: Optional[Path] = None,
                 external_apps_file: Optional[Path] = None):
        """
        Initialize processor with raw data and field mappings.

        Args:
            raw_data: List of CMDB records
            field_mappings: Column name mappings
            aliases_file: Path to mqmanager_aliases.json
            app_to_qmgr_file: Path to app_to_qmgr.json (for known internal apps)
            external_apps_file: Path to external_apps.json (for known external apps)
        """
        if not isinstance(raw_data, list):
            raise ValueError(f"Input data must be a list, got {type(raw_data)}")

        if len(raw_data) == 0:
            raise ValueError("Input data list is empty")

        self.raw_data = raw_data
        self.field_mappings = field_mappings

        # Collections for processing
        self.valid_mqmanagers = set()
        self.mqmanager_to_directorate = {}

        # Alias mappings: alias -> canonical name
        self.alias_to_canonical: Dict[str, str] = {}
        self.canonical_to_aliases: Dict[str, Set[str]] = defaultdict(set)

        # Application mappings
        self.known_apps: Dict[str, str] = {}  # app_name -> 'Internal' or 'External'
        self.app_name_set: Set[str] = set()   # Set of all app names (uppercase)

        self.stats = {
            'total_records': len(self.raw_data),
            'processed_sender': 0,
            'processed_receiver': 0,
            'inbound_found': 0,
            'outbound_found': 0,
            'inbound_extra_found': 0,
            'outbound_extra_found': 0,
            'inbound_apps_found': 0,
            'outbound_apps_found': 0,
            'aliases_resolved': 0
        }

        # Load aliases if file provided
        if aliases_file and aliases_file.exists():
            self._load_aliases(aliases_file)

        # Load applications if files provided
        if app_to_qmgr_file and app_to_qmgr_file.exists():
            self._load_internal_apps(app_to_qmgr_file)

        if external_apps_file and external_apps_file.exists():
            self._load_external_apps(external_apps_file)

        logger.info(f"✓ Initialized with {len(self.raw_data)} records")
        if self.alias_to_canonical:
            logger.info(f"✓ Loaded {len(self.alias_to_canonical)} MQ Manager aliases")
        if self.known_apps:
            logger.info(f"✓ Loaded {len(self.known_apps)} known applications")

    def _load_aliases(self, aliases_file: Path):
        """Load MQ Manager aliases from JSON file."""
        try:
            with open(aliases_file, 'r', encoding='utf-8') as f:
                aliases_data = json.load(f)

            for entry in aliases_data:
                canonical = entry.get('canonical', '').strip().upper()
                aliases = entry.get('aliases', [])

                if canonical:
                    # Map canonical to itself
                    self.alias_to_canonical[canonical] = canonical

                    for alias in aliases:
                        alias_upper = alias.strip().upper()
                        if alias_upper:
                            self.alias_to_canonical[alias_upper] = canonical
                            self.canonical_to_aliases[canonical].add(alias_upper)
        except Exception as e:
            logger.warning(f"Warning: Could not load aliases file: {e}")

    def _load_internal_apps(self, app_file: Path):
        """Load internal applications from app_to_qmgr.json."""
        try:
            with open(app_file, 'r', encoding='utf-8') as f:
                apps_data = json.load(f)

            for entry in apps_data:
                app_name = entry.get('Application', '').strip()
                if app_name:
                    app_upper = app_name.upper()
                    self.known_apps[app_upper] = 'Internal'
                    self.app_name_set.add(app_upper)
        except Exception as e:
            logger.warning(f"Warning: Could not load app_to_qmgr file: {e}")

    def _load_external_apps(self, external_file: Path):
        """Load external applications from external_apps.json."""
        try:
            with open(external_file, 'r', encoding='utf-8') as f:
                apps_data = json.load(f)

            for entry in apps_data:
                app_name = entry.get('name', '').strip()
                app_type = entry.get('type', 'External')
                if app_name:
                    app_upper = app_name.upper()
                    self.known_apps[app_upper] = app_type
                    self.app_name_set.add(app_upper)
        except Exception as e:
            logger.warning(f"Warning: Could not load external_apps file: {e}")

    def _resolve_alias(self, mqmanager: str) -> str:
        """Resolve an MQ Manager name to its canonical form."""
        if not mqmanager:
            return mqmanager
        mqmanager_upper = mqmanager.upper()
        canonical = self.alias_to_canonical.get(mqmanager_upper)
        if canonical and canonical != mqmanager_upper:
            self.stats['aliases_resolved'] += 1
            return canonical
        return mqmanager_upper
   
    def _normalize_value(self, val) -> str:
        """Normalize string values."""
        if val is None:
            return ""
        return str(val).strip()

    def _find_app_in_string(self, text: str) -> Optional[tuple]:
        """
        Check if the text matches or contains a known application name.

        Returns:
            Tuple of (app_name, app_type) if found, None otherwise
        """
        if not text:
            return None

        text_upper = text.upper()

        # Check if the entire string matches an app name
        if text_upper in self.app_name_set:
            return (text, self.known_apps.get(text_upper, 'Unknown'))

        # Check if any part (split by dots) matches an app name
        parts = text.split('.')
        for part in parts:
            part_upper = part.upper()
            if part_upper in self.app_name_set:
                return (part, self.known_apps.get(part_upper, 'Unknown'))

        return None
   
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
        Check if any valid MQmanager name (or alias) exists in the text.
        Returns the canonical MQmanager name if found, None otherwise.
        """
        if not text:
            return None

        text_upper = text.upper()
        exclude_upper = self._resolve_alias(exclude_mqmanager)

        # Split by dots and check each part
        parts = text.split('.')
        for part in parts:
            part_upper = part.upper()

            # First check if it's an alias and resolve it
            canonical = self.alias_to_canonical.get(part_upper)
            if canonical:
                if canonical != exclude_upper:
                    return canonical
                continue

            # Then check if it's a valid MQ manager directly
            if part_upper in self.valid_mqmanagers and part_upper != exclude_upper:
                return part

        # Check if entire string matches (or is an alias)
        canonical = self.alias_to_canonical.get(text_upper)
        if canonical and canonical != exclude_upper:
            return canonical

        if text_upper in self.valid_mqmanagers and text_upper != exclude_upper:
            return text

        return None
   
    def _build_index(self):
        """First pass: collect all valid MQmanager names and their aliases."""
        logger.info("Building MQ Manager index...")

        for record in self.raw_data:
            if not isinstance(record, dict):
                continue

            mqmanager_field = self.field_mappings.get('mqmanager', 'MQmanager')
            directorate_field = self.field_mappings.get('directorate', 'directorate')

            mqmanager = self._normalize_value(record.get(mqmanager_field, ''))

            if mqmanager:
                mqmanager_upper = mqmanager.upper()

                # Resolve alias to canonical name
                canonical = self._resolve_alias(mqmanager)

                # Add both the original and canonical to valid_mqmanagers
                self.valid_mqmanagers.add(mqmanager_upper)
                if canonical != mqmanager_upper:
                    self.valid_mqmanagers.add(canonical)

                directorate = self._normalize_value(record.get(directorate_field, ''))
                if not directorate:
                    directorate = "Unknown"

                # Store both original and canonical with same directorate
                self.mqmanager_to_directorate[mqmanager_upper] = directorate
                if canonical != mqmanager_upper:
                    self.mqmanager_to_directorate[canonical] = directorate

        # Also add all known aliases to valid_mqmanagers
        for alias in self.alias_to_canonical.keys():
            self.valid_mqmanagers.add(alias)

        logger.info(f"✓ Found {len(self.valid_mqmanagers)} unique MQ Managers (including aliases)")
   
    def process_assets(self) -> Dict:
        """
        Process all assets and extract relationships - ORIGINAL WORKING LOGIC.
        Returns: {directorate: {mqmanager: {...}}}

        Now includes:
        - Alias resolution for MQ Manager names
        - Application detection (inbound_apps, outbound_apps)
        - Internal vs External application classification
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
            'outbound_extra': set(),
            'inbound_apps': set(),       # Apps that send TO this MQ manager
            'outbound_apps': set(),      # Apps that receive FROM this MQ manager
            'inbound_apps_external': set(),   # External apps sending to this MQ manager
            'outbound_apps_external': set()   # External apps receiving from this MQ manager
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
                    # Check if remaining contains another MQmanager (with alias resolution)
                    found_mqmanager = self._find_mqmanager_in_string(remaining, mqmanager)

                    if found_mqmanager:
                        # Resolve alias to canonical name
                        canonical_found = self._resolve_alias(found_mqmanager)
                        canonical_current = self._resolve_alias(mqmanager)

                        # This MQmanager sends TO found_mqmanager -> Outbound
                        directorate_data[directorate][mqmanager]['outbound'].add(canonical_found)
                        self.stats['outbound_found'] += 1

                        # INVERSE: found_mqmanager receives FROM this mqmanager
                        target_dir = self.mqmanager_to_directorate.get(canonical_found, "Unknown")
                        directorate_data[target_dir][canonical_found]['inbound'].add(canonical_current)
                    else:
                        # No MQmanager found - check if it's a known application
                        app_info = self._find_app_in_string(remaining)

                        if app_info:
                            app_name, app_type = app_info
                            if app_type == 'External':
                                directorate_data[directorate][mqmanager]['outbound_apps_external'].add(app_name)
                            else:
                                directorate_data[directorate][mqmanager]['outbound_apps'].add(app_name)
                            self.stats['outbound_apps_found'] += 1
                        else:
                            # Unknown destination -> Outbound_Extra
                            directorate_data[directorate][mqmanager]['outbound_extra'].add(remaining)
                            self.stats['outbound_extra_found'] += 1

            elif 'RECEIVER' in role and asset:
                self.stats['processed_receiver'] += 1

                # Extract remaining string after removing MQmanager
                remaining = self._extract_mqmanager_from_asset(asset, mqmanager)

                if remaining:
                    # Check if remaining contains another MQmanager (with alias resolution)
                    found_mqmanager = self._find_mqmanager_in_string(remaining, mqmanager)

                    if found_mqmanager:
                        # Resolve alias to canonical name
                        canonical_found = self._resolve_alias(found_mqmanager)
                        canonical_current = self._resolve_alias(mqmanager)

                        # This MQmanager receives FROM found_mqmanager -> Inbound
                        directorate_data[directorate][mqmanager]['inbound'].add(canonical_found)
                        self.stats['inbound_found'] += 1

                        # INVERSE: found_mqmanager sends TO this mqmanager
                        target_dir = self.mqmanager_to_directorate.get(canonical_found, "Unknown")
                        directorate_data[target_dir][canonical_found]['outbound'].add(canonical_current)
                    else:
                        # No MQmanager found - check if it's a known application
                        app_info = self._find_app_in_string(remaining)

                        if app_info:
                            app_name, app_type = app_info
                            if app_type == 'External':
                                directorate_data[directorate][mqmanager]['inbound_apps_external'].add(app_name)
                            else:
                                directorate_data[directorate][mqmanager]['inbound_apps'].add(app_name)
                            self.stats['inbound_apps_found'] += 1
                        else:
                            # Unknown source -> Inbound_Extra
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
                    'outbound_extra': sorted(list(data['outbound_extra'])),
                    'inbound_apps': sorted(list(data.get('inbound_apps', set()))),
                    'outbound_apps': sorted(list(data.get('outbound_apps', set()))),
                    'inbound_apps_external': sorted(list(data.get('inbound_apps_external', set()))),
                    'outbound_apps_external': sorted(list(data.get('outbound_apps_external', set())))
                }

        return result
   
    def print_stats(self):
        """Print processing statistics."""
        logger.info("=" * 70)
        logger.info("PROCESSING STATISTICS")
        logger.info("=" * 70)
        logger.info(f"Total records:           {self.stats['total_records']}")
        logger.info(f"Sender records:          {self.stats['processed_sender']}")
        logger.info(f"Receiver records:        {self.stats['processed_receiver']}")
        logger.info("-" * 70)
        logger.info(f"Inbound connections:     {self.stats['inbound_found']}")
        logger.info(f"Outbound connections:    {self.stats['outbound_found']}")
        logger.info(f"Inbound_Extra:           {self.stats['inbound_extra_found']}")
        logger.info(f"Outbound_Extra:          {self.stats['outbound_extra_found']}")
        logger.info("-" * 70)
        logger.info(f"Inbound Apps found:      {self.stats['inbound_apps_found']}")
        logger.info(f"Outbound Apps found:     {self.stats['outbound_apps_found']}")
        logger.info(f"Aliases resolved:        {self.stats['aliases_resolved']}")
        logger.info("=" * 70)