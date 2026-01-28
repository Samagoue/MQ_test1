"""Data deduplication logic."""

from typing import List, Dict
from config.settings import Config


def deduplicate_assets(data: List[Dict]) -> List[Dict]:
    """
    Convenience function for asset deduplication using default config.

    Args:
        data: List of asset records

    Returns:
        Deduplicated list of asset records
    """
    deduplicator = AssetDeduplicator(
        asset_field=Config.DEDUP_ASSET_FIELD,
        ignore_type=Config.DEDUP_IGNORE_TYPE
    )
    return deduplicator.deduplicate(data)


class AssetDeduplicator:
    """Remove duplicate assets based on business rules."""
   
    def __init__(self, asset_field: str = "asset", ignore_type: str = "QCluster"):
        self.asset_field = asset_field
        self.ignore_type = ignore_type
   
    def deduplicate(self, data: List[Dict]) -> List[Dict]:
        """
        Remove duplicates based on rules.
       
        Rule: If asset is duplicated and one record has asset_type = 'QCluster',
              ignore the QCluster record and keep the other one.
        """
        if not data or self.asset_field not in data[0]:
            return data
       
        # Group by asset
        asset_groups = {}
        for record in data:
            asset = record.get(self.asset_field)
            if asset not in asset_groups:
                asset_groups[asset] = []
            asset_groups[asset].append(record)
       
        # Apply deduplication
        deduplicated = []
        for asset, records in asset_groups.items():
            if len(records) == 1:
                deduplicated.append(records[0])
            else:
                # Keep non-QCluster records
                non_qcluster = [r for r in records if r.get('asset_type') != self.ignore_type]
                deduplicated.extend(non_qcluster if non_qcluster else [records[0]])
       
        return deduplicated
