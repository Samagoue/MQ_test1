import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class ApplicationDiagramStep(PipelineStep):
    name        = "Application Diagrams"
    step_number = "7"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from generators.application_diagram_generator import ApplicationDiagramGenerator

        gen = ApplicationDiagramGenerator(ctx.enriched_data, ctx.config)
        count = gen.generate_all(ctx.config.APPLICATION_DIAGRAMS_DIR, workers=ctx.workers)
        if count > 0:
            logger.info(f"  Generated {count} application diagrams in {ctx.config.APPLICATION_DIAGRAMS_DIR}")
            if not ctx.pdf_generated:
                logger.warning("  ⚠ GraphViz required for PDF generation")
        else:
            logger.warning("  ⚠ No application diagrams generated")
