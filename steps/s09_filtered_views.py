import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class FilteredViewsStep(PipelineStep):
    name        = "Smart Filtered Views"
    step_number = "9"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from utils.smart_filter import generate_filtered_diagrams

        count = generate_filtered_diagrams(ctx.enriched_data, ctx.config.FILTERED_VIEWS_DIR, ctx.config)
        if count > 0:
            logger.info(f"  Generated {count} filtered view diagrams in {ctx.config.FILTERED_VIEWS_DIR}")
            logger.info("  Views: per-organization, gateways-only, internal/external gateways")
        else:
            logger.warning("  ⚠ No filtered views generated")
