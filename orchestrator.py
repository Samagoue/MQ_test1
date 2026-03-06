"""
MQ CMDB Pipeline Orchestrator

Coordinates the processing pipeline via the open-architecture step registry
defined in steps/__init__.py.

Each pipeline step is an independent PipelineStep subclass that reads from
and writes to a shared PipelineContext.  To add, remove, or reorder steps,
edit steps/__init__.py — no changes to this file are required.
"""

import os
import sys
import traceback
from datetime import datetime

from config.settings import Config
from core.interfaces import PipelineContext
from steps import PIPELINE_STEPS
from steps.s14_notification import NotificationStep
from utils.common import setup_utf8_output
from utils.logging_config import get_logger

logger = get_logger("orchestrator")


class MQCMDBOrchestrator:
    """Orchestrate the complete MQ CMDB processing pipeline."""

    def __init__(
        self,
        skip_export:   bool = False,
        diagrams_only: bool = False,
        workers:       int  = None,
        dry_run:       bool = False,
    ):
        """
        Args:
            skip_export:   Skip database export; use existing data.
            diagrams_only: Only regenerate diagrams from processed data.
            workers:       Parallel workers for diagram generation (None = sequential).
            dry_run:       Log planned actions without executing.
        """
        setup_utf8_output()
        Config.ensure_directories()

        self.skip_export   = skip_export
        self.diagrams_only = diagrams_only
        self.dry_run       = dry_run

        # Resolve workers: CLI flag > env var > Config default
        if workers is not None:
            self.workers = workers
        elif os.environ.get("MQCMDB_WORKERS"):
            try:
                self.workers = int(os.environ["MQCMDB_WORKERS"])
            except ValueError:
                self.workers = Config.PARALLEL_WORKERS
        else:
            self.workers = Config.PARALLEL_WORKERS

    # ------------------------------------------------------------------ #

    def run_full_pipeline(self) -> bool:
        """Execute the full pipeline.  Returns True on success."""
        logger.info("\n" + "=" * 70)
        logger.info("MQ CMDB HIERARCHICAL AUTOMATION PIPELINE")
        logger.info("=" * 70)

        success       = False
        error_message = None

        ctx = PipelineContext(
            config        = Config,
            timestamp     = datetime.now().strftime("%Y%m%d_%H%M%S"),
            workers       = self.workers,
            dry_run       = self.dry_run,
            skip_export   = self.skip_export,
            diagrams_only = self.diagrams_only,
        )

        try:
            n = len(PIPELINE_STEPS)
            for step in PIPELINE_STEPS:
                logger.info(f"\n[{step.step_number}/{n}] {step.name}...")

                if not step.should_run(ctx):
                    logger.info("  Skipped")
                    continue

                if ctx.dry_run:
                    logger.info("  (dry-run — skipped)")
                    continue

                try:
                    step.run(ctx)
                except Exception as e:
                    logger.warning(f"  ⚠ {step.name} failed: {e}")
                    ctx.errors.append(f"{step.name}: {e}")

            logger.info("\n" + "=" * 70)
            logger.info("✓ PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 70)
            success = True

        except FileNotFoundError as e:
            logger.error(f"\n✗ ERROR: {e}")
            logger.info("Ensure all required files exist in the correct directories")
            error_message = f"File not found: {e}"
        except Exception as e:
            logger.error(f"\n✗ UNEXPECTED ERROR: {e}")
            error_message = f"Unexpected error: {e}\n{traceback.format_exc()}"
            logger.exception("Unexpected pipeline error")

        # Notification step always runs (handled separately from the loop
        # so it receives the final success/error state)
        self._send_notification(ctx, success, error_message)

        return success

    # ------------------------------------------------------------------ #

    @staticmethod
    def _send_notification(ctx: PipelineContext, success: bool, error_message: str = None):
        """Delegate to the notification step with final pipeline outcome."""
        notif = next((s for s in PIPELINE_STEPS if isinstance(s, NotificationStep)), None)
        if notif is None:
            return
        notif.success       = success
        notif.error_message = error_message
        try:
            notif.run(ctx)
        except Exception as e:
            logger.warning(f"  ⚠ Email notification error: {e}")


# --------------------------------------------------------------------------- #

def main():
    """Entry point for the MQ CMDB orchestrator."""
    orchestrator = MQCMDBOrchestrator()
    success = orchestrator.run_full_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
