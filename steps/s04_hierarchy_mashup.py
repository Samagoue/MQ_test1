import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class HierarchyMashupStep(PipelineStep):
    name        = "Enrich with Org Hierarchy"
    step_number = "4"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.directorate_data)

    def run(self, ctx: PipelineContext) -> None:
        from processors.hierarchy_mashup import HierarchyMashup
        from utils.file_io import save_json

        mashup = HierarchyMashup(
            ctx.config.ORG_HIERARCHY_JSON,
            ctx.config.APP_TO_QMGR_JSON,
            ctx.config.GATEWAYS_JSON,
            ctx.config.HOSTS_JSON,
            ctx.config.ROUTERS_JSON,
        )
        ctx.enriched_data = mashup.enrich_data(ctx.directorate_data)
        save_json(ctx.enriched_data, ctx.config.PROCESSED_JSON)
        logger.info(f"  Enriched data saved: {ctx.config.PROCESSED_JSON}")
