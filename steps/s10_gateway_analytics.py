import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class GatewayAnalyticsStep(PipelineStep):
    name        = "Gateway Analytics"
    step_number = "10"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from analytics.gateway_analyzer import GatewayAnalyzer, generate_gateway_report_html
        from utils.file_io import save_json

        analyzer = GatewayAnalyzer(ctx.enriched_data)
        ctx.gateway_analytics = analyzer.analyze()

        if ctx.gateway_analytics["summary"]["total_gateways"] > 0:
            analytics_report = ctx.config.REPORTS_DIR / f"gateway_analytics_{ctx.timestamp}.html"
            generate_gateway_report_html(ctx.gateway_analytics, analytics_report)

            analytics_json = ctx.config.DATA_DIR / f"gateway_analytics_{ctx.timestamp}.json"
            save_json(ctx.gateway_analytics, analytics_json)

            logger.info(f"  {ctx.gateway_analytics['summary']['total_gateways']} gateways analyzed")
            logger.info(f"  Report: {analytics_report}")
        else:
            logger.warning("  ⚠ No gateways found in data")
