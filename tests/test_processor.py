#!/usr/bin/env python3
"""
Test MQ Manager Processor with sample data.
Used by GitLab CI/CD pipeline.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processors.mqmanager_processor import MQManagerProcessor
from config.settings import Config


def test_processor():
    """Test the MQ Manager Processor with sample data."""

    # Sample test data
    sample_data = [
        {
            "MQmanager": "QM_TEST_01",
            "asset": "QM_TEST_01.QM_TEST_02.QUEUE",
            "asset_type": "Queue Remote",
            "directorate": "IT_DEPT",
            "Role": "SENDER"
        },
        {
            "MQmanager": "QM_TEST_02",
            "asset": "QM_TEST_02.QM_TEST_01.QUEUE",
            "asset_type": "Queue Local",
            "directorate": "IT_DEPT",
            "Role": "RECEIVER"
        }
    ]

    print("Testing MQ Manager Processor with sample data...")
    print("-" * 50)

    try:
        processor = MQManagerProcessor(sample_data, Config.FIELD_MAPPINGS)

        result = processor.process_assets()
        json_result = processor.convert_to_json(result)
        processor.print_stats()

        # Verify results
        assert 'IT_DEPT' in json_result, "Expected IT_DEPT directorate in results"
        assert 'QM_TEST_01' in json_result['IT_DEPT'], "Expected QM_TEST_01 in results"
        assert 'QM_TEST_02' in json_result['IT_DEPT'], "Expected QM_TEST_02 in results"

        print("\nProcessor test PASSED")
        return 0

    except Exception as e:
        print(f"\nProcessor test FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(test_processor())
