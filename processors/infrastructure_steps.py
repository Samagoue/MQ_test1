"""
Infrastructure pipeline steps.

These steps handle the pipeline's setup and teardown duties that don't belong
to a specific domain module:

    OutputCleanupStep   — deletes old timestamped output files (step 0)
    DataIngestionStep   — loads raw JSON + builds host/alias lookup maps (step 1)
    ConfluenceSyncStep  — pulls input files from Confluence before enrichment (step 3.5)

All three self-register with the PluginRegistry so the orchestrator discovers
them automatically alongside all other steps.
"""

from datetime import datetime
from pathlib import Path

from core.interfaces import PipelineContext, Processor
from core.registry import PluginRegistry
from utils.file_io import load_json, cleanup_output_directory
from utils.logging_config import get_logger

logger = get_logger("processors.infrastructure")


# ──────────────────────────────────────────────────────────────────────────────
# Step 0 — Output cleanup
# ──────────────────────────────────────────────────────────────────────────────

@PluginRegistry.register(order=0)
class OutputCleanupStep(Processor):
    """Delete output files older than Config.OUTPUT_RETENTION_DAYS (step 0).

    Runs only when Config.ENABLE_OUTPUT_CLEANUP is True.
    Failures are non-fatal: a warning is logged and the pipeline continues.
    """

    name             = "Output Cleanup"
    abort_on_failure = False    # stale files are inconvenient, not fatal

    def execute(self, context: PipelineContext) -> None:
        config = context.config
        if not config.ENABLE_OUTPUT_CLEANUP:
            logger.info("  Output cleanup disabled (ENABLE_OUTPUT_CLEANUP=False)")
            return

        try:
            results = cleanup_output_directory(
                config.OUTPUT_DIR,
                config.OUTPUT_RETENTION_DAYS,
                config.OUTPUT_CLEANUP_PATTERNS,
            )
            if results['total_deleted'] > 0:
                logger.info(
                    f"✓ Cleaned up {results['total_deleted']} old file(s) "
                    f"(>{config.OUTPUT_RETENTION_DAYS} days)"
                )
                for fname in results['deleted_files'][:5]:
                    logger.info(f"  - {fname}")
                if len(results['deleted_files']) > 5:
                    logger.info(f"  ... and {len(results['deleted_files']) - 5} more")
            else:
                logger.info("✓ No old files to clean up")

            for error in results.get('errors', []):
                logger.warning(f"⚠ {error}")

        except Exception as exc:
            context.record_error(self.name, exc)


# ──────────────────────────────────────────────────────────────────────────────
# Step 1 — Data ingestion
# ──────────────────────────────────────────────────────────────────────────────

@PluginRegistry.register(order=1)
class DataIngestionStep(Processor):
    """Load raw MQ CMDB JSON and build host / alias lookup maps (step 1).

    Writes to context:
        raw_data             — list of raw asset records
        host_directorate_map — hostname → owning directorate
        alias_to_canonical   — MQ Manager alias → canonical name
        timestamp            — YYYYMMDD_HHMMSS string for output file naming

    abort_on_failure=True: the pipeline cannot proceed without raw_data.
    """

    name             = "Load MQ CMDB Data"
    abort_on_failure = True

    def execute(self, context: PipelineContext) -> None:
        config = context.config

        # Timestamp used throughout the pipeline for naming output files.
        context.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # ── Load primary dataset ──────────────────────────────────────────
        context.raw_data = load_json(config.INPUT_JSON)
        logger.info(f"✓ Loaded {len(context.raw_data)} records")

        # ── Hostname → directorate map ────────────────────────────────────
        # The host_directorate field is a more reliable owner indicator than
        # the asset-level directorate field for determining a QM's department.
        if config.HOSTS_JSON.exists():
            hosts_data = load_json(config.HOSTS_JSON)
            for h in hosts_data:
                hostname = str(h.get('hostname', '')).strip()
                host_dir = str(h.get('host_directorate', '')).strip()
                if hostname and host_dir:
                    context.host_directorate_map[hostname.upper()] = host_dir
            logger.info(
                f"✓ Host→directorate map: {len(context.host_directorate_map)} entries"
            )
        else:
            logger.warning(
                "⚠ all_cmdb_hosts.json not found — "
                "QM directorate will use asset-level fallback"
            )

        # ── Alias → canonical name map ────────────────────────────────────
        if config.MQMANAGER_ALIASES_JSON.exists():
            aliases_data = load_json(config.MQMANAGER_ALIASES_JSON)
            for entry in aliases_data:
                canonical = str(entry.get('canonical', '')).strip()
                for alias in entry.get('aliases', []):
                    alias = str(alias).strip()
                    if alias and canonical:
                        context.alias_to_canonical[alias.upper()] = canonical
            logger.info(
                f"✓ Alias map: {len(context.alias_to_canonical)} alias(es) loaded"
            )
        else:
            logger.info("  No mqmanager_aliases.json found — alias resolution skipped")


# ──────────────────────────────────────────────────────────────────────────────
# Step 3.5 — Confluence input-file sync
# ──────────────────────────────────────────────────────────────────────────────

@PluginRegistry.register(order=3.5)
class ConfluenceSyncStep(Processor):
    """Pull input JSON files from Confluence before hierarchy enrichment (step 3.5).

    Runs only when Confluence is configured (confluence_config.json present and
    valid). Failures are non-fatal — existing local files are preserved so the
    pipeline can continue with the last-known-good data.
    """

    name             = "Confluence Input File Sync"
    abort_on_failure = False

    def execute(self, context: PipelineContext) -> None:
        try:
            from utils.confluence_shim import is_configured, sync_input_files
        except ImportError:
            logger.info("  confluence_shim not available — skipping sync")
            return

        if not is_configured():
            logger.info("  Confluence not configured — skipping input file sync")
            return

        try:
            result = sync_input_files()
            if result["synced"] > 0:
                logger.info(f"✓ Synced {result['synced']} input file(s) from Confluence")
            if result["errors"] > 0:
                logger.warning(
                    f"⚠ {result['errors']} input file(s) failed to sync "
                    "— using existing local files"
                )
        except Exception as exc:
            context.record_error(self.name, exc)
