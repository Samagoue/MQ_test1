from core.interfaces import PipelineContext, PipelineStep


class OutputCleanupStep(PipelineStep):
    name        = "Output Cleanup"
    step_number = "0"

    def should_run(self, ctx: PipelineContext) -> bool:
        return ctx.config.ENABLE_OUTPUT_CLEANUP

    def run(self, ctx: PipelineContext) -> None:
        from utils.file_io import cleanup_output_directory
        import logging
        logger = logging.getLogger(__name__)

        results = cleanup_output_directory(
            ctx.config.OUTPUT_DIR,
            ctx.config.OUTPUT_RETENTION_DAYS,
            ctx.config.OUTPUT_CLEANUP_PATTERNS,
        )
        if results["total_deleted"] > 0:
            logger.info(f"  Cleaned up {results['total_deleted']} old file(s) (>{ctx.config.OUTPUT_RETENTION_DAYS} days)")
            for fname in results["deleted_files"][:5]:
                logger.info(f"  - {fname}")
            if len(results["deleted_files"]) > 5:
                logger.info(f"  ... and {len(results['deleted_files']) - 5} more")
        else:
            logger.info("  No old files to clean up")

        for error in results.get("errors", []):
            logger.warning(f"  ⚠ {error}")
