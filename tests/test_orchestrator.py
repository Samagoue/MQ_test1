#!/usr/bin/env python3
"""
Test Orchestrator initialization.
Used by GitLab CI/CD pipeline.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config


def test_orchestrator():
    """Test orchestrator initialization (not full run - no data)."""

    print("Testing orchestrator initialization...")
    print("-" * 50)

    # Ensure directories exist
    Config.ensure_directories()
    print("Directories created successfully")

    try:
        from orchestrator import MQCMDBOrchestrator

        # This will fail because no input data exists
        # but it tests that all imports and config work
        orchestrator = MQCMDBOrchestrator()
        print("Orchestrator initialized successfully")
        print("Note: Full pipeline requires input data file")
        return 0

    except FileNotFoundError as e:
        # This is expected - no input data in CI
        print(f"Expected error (no input data): {e}")
        print("Orchestrator imports and config work correctly")
        return 0

    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(test_orchestrator())
