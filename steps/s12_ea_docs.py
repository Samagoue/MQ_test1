import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class EADocumentationStep(PipelineStep):
    name        = "EA Documentation"
    step_number = "12"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from generators.doc_generator import EADocumentationGenerator

        out = ctx.config.EXPORTS_DIR / f"EA_Documentation_{ctx.timestamp}.txt"
        EADocumentationGenerator(ctx.enriched_data).generate(out)
        logger.info(f"  EA Documentation: {out}")
        logger.info("  → Import into Confluence using Insert → Markup")

        try:
            from utils.confluence_shim import publish_ea_documentation
            publish_ea_documentation(out)
        except Exception as pub_e:
            logger.warning(f"  ⚠ Confluence publish skipped: {pub_e}")
