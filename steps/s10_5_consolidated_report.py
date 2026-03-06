import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class ConsolidatedReportStep(PipelineStep):
    name        = "Consolidated Report"
    step_number = "10.5"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from utils.report_consolidator import generate_consolidated_report

        consolidated_file = ctx.config.REPORTS_DIR / f"consolidated_report_{ctx.timestamp}.html"

        generate_consolidated_report(
            changes=ctx.changes,
            gateway_analytics=ctx.gateway_analytics,
            output_file=consolidated_file,
            current_timestamp=ctx.timestamp,
            baseline_timestamp=ctx.baseline_time_str,
            enriched_data=ctx.enriched_data,
        )
        ctx.consolidated_report_file = consolidated_file
        logger.info(f"  Consolidated report: {consolidated_file}")
