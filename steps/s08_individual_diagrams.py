import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class IndividualDiagramStep(PipelineStep):
    name        = "Individual MQ Manager Diagrams"
    step_number = "8"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.directorate_data)

    def run(self, ctx: PipelineContext) -> None:
        from generators.graphviz_individual import IndividualDiagramGenerator

        gen = IndividualDiagramGenerator(ctx.directorate_data, ctx.config)
        count = gen.generate_all(ctx.config.INDIVIDUAL_DIAGRAMS_DIR, workers=ctx.workers)
        if count > 0:
            logger.info(f"  Generated {count} individual MQ manager diagrams in {ctx.config.INDIVIDUAL_DIAGRAMS_DIR}")
            if not ctx.pdf_generated:
                logger.warning("  ⚠ GraphViz required for PDF generation")
        else:
            logger.warning("  ⚠ No individual diagrams generated")
