"""MQ CMDB Pipeline Orchestrator — Open Architecture Edition.

Generic registry-driven runner.  Every pipeline step is discovered
automatically from the PluginRegistry; no component class is imported here
by name.  To add a new step, create a new file in processors/, generators/,
analytics/, or utils/ and decorate its class with
    @PluginRegistry.register(order=N)

See core/registry.py for the full numbering convention.
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import Config
from core.interfaces import PipelineContext
from core.registry import PluginRegistry
from utils.common import setup_utf8_output
from utils.logging_config import setup_logging, get_logger

logger = get_logger("orchestrator")


class MQCMDBOrchestrator:
    """Generic registry-driven pipeline runner."""

    def __init__(self):
        setup_utf8_output()
        Config.ensure_directories()

    # ──────────────────────────────────────────────────────────────────────
    # Public entry-point
    # ──────────────────────────────────────────────────────────────────────

    def run_full_pipeline(self) -> bool:
        """Execute the complete pipeline and return True on success."""
        logger.info("\n" + "=" * 70)
        logger.info("MQ CMDB HIERARCHICAL AUTOMATION PIPELINE")
        logger.info("=" * 70)

        # Log all registered steps at startup for visibility
        logger.info(PluginRegistry.summary())

        context = PipelineContext(config=Config, logger=logger)

        all_steps = PluginRegistry.get_ordered_steps()

        # EmailNotifierStep (order=14) is treated specially:
        # it always runs in a finally block, even when the pipeline fails.
        notify_steps = [s for s in all_steps if getattr(s, '_order', 0) == 14]
        main_steps   = self._filter_enabled(
            [s for s in all_steps if getattr(s, '_order', 0) != 14]
        )

        success = False
        try:
            self._run_steps(main_steps, context)
            self._print_summary(context)

            logger.info("\n" + "=" * 70)
            logger.info("✓ PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 70)
            success = True

        except _PipelineAborted as exc:
            logger.error(f"\n✗ PIPELINE ABORTED: {exc}")

        except FileNotFoundError as exc:
            logger.error(f"\n✗ ERROR: {exc}")
            logger.info("Ensure all required files exist in the correct directories")

        except Exception as exc:
            logger.error(f"\n✗ UNEXPECTED ERROR: {exc}")
            logger.exception("Unexpected pipeline error")

        finally:
            # Notification always runs — pass success flag via context errors list
            # (non-empty pipeline_errors may indicate partial success)
            for StepClass in self._filter_enabled(notify_steps):
                try:
                    StepClass().execute(context)
                except Exception as exc:
                    logger.warning(f"⚠ Notification step failed: {exc}")

        return success

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _filter_enabled(self, steps):
        """Remove steps that are disabled in Config.PIPELINE_STEPS."""
        enabled = []
        for StepClass in steps:
            key = StepClass.__name__
            if Config.PIPELINE_STEPS.get(key, True):
                enabled.append(StepClass)
            else:
                logger.debug(f"  Step '{key}' disabled in PIPELINE_STEPS — skipping")
        return enabled

    def _run_steps(self, steps, context: PipelineContext) -> None:
        """Execute steps in order, running same-group steps concurrently."""
        for group_key, batch in PluginRegistry.iter_groups(steps):
            if group_key:
                # Parallel: submit all steps in this group to a thread pool
                logger.info(
                    f"\nRunning parallel group '{group_key}' "
                    f"({len(batch)} step(s))..."
                )
                with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                    futures = {
                        pool.submit(self._safe_execute, S, context): S
                        for S in batch
                    }
                    for fut in as_completed(futures):
                        fut.result()   # propagates _PipelineAborted if raised
            else:
                # Sequential: one step at a time
                for StepClass in batch:
                    self._safe_execute(StepClass, context)

    def _safe_execute(self, StepClass, context: PipelineContext) -> None:
        """Run one step, honouring abort_on_failure."""
        name = getattr(StepClass, 'name', '') or StepClass.__name__
        try:
            StepClass().execute(context)
        except Exception as exc:
            if getattr(StepClass, 'abort_on_failure', False):
                raise _PipelineAborted(f"[{name}] {exc}") from exc
            # Non-fatal — record and continue
            context.record_error(name, exc)

    def _print_summary(self, context: PipelineContext) -> None:
        """Print statistics derived from enriched_data on context."""
        enriched = context.enriched_data or {}
        stats = {
            "Organizations":     len(enriched),
            "Departments":       0,
            "Business Owners":   0,
            "Applications":      0,
            "MQ Managers":       0,
            "Total QLocal":      0,
            "Total QRemote":     0,
            "Total QAlias":      0,
            "Total Connections": 0,
        }

        for org_data in enriched.values():
            departments = org_data.get('_departments', {})
            stats["Departments"] += len(departments)
            for biz_owners in departments.values():
                stats["Business Owners"] += len(biz_owners)
                for applications in biz_owners.values():
                    stats["Applications"] += len(applications)
                    for mqmanagers in applications.values():
                        stats["MQ Managers"] += len(mqmanagers)
                        for mq_data in mqmanagers.values():
                            stats["Total QLocal"]       += mq_data.get('qlocal_count', 0)
                            stats["Total QRemote"]      += mq_data.get('qremote_count', 0)
                            stats["Total QAlias"]       += mq_data.get('qalias_count', 0)
                            stats["Total Connections"]  += len(mq_data.get('outbound', []))

        logger.info("\n" + "-" * 70)
        logger.info("[13/14] SUMMARY STATISTICS")
        logger.info("-" * 70)
        for key, value in stats.items():
            logger.info(f"{key + ':':21} {value}")
        logger.info("-" * 70)

        if context.pipeline_errors:
            logger.info("\nWarnings during execution:")
            for err in context.pipeline_errors:
                logger.info(f"  ⚠ {err}")


# ──────────────────────────────────────────────────────────────────────────────
# Internal sentinel exception
# ──────────────────────────────────────────────────────────────────────────────

class _PipelineAborted(RuntimeError):
    """Raised by _safe_execute when a critical step (abort_on_failure=True) fails."""


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    """Entry point for the MQ CMDB orchestrator."""
    setup_logging(banner_config=Config.BANNER_CONFIG)
    orchestrator = MQCMDBOrchestrator()
    success = orchestrator.run_full_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
