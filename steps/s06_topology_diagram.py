import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class TopologyDiagramStep(PipelineStep):
    name        = "Hierarchical Topology Diagram"
    step_number = "6"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from generators.graphviz_hierarchical import HierarchicalGraphVizGenerator

        gen = HierarchicalGraphVizGenerator(ctx.enriched_data, ctx.config)
        gen.save_to_file(ctx.config.TOPOLOGY_DOT)

        ctx.pdf_generated = gen.generate_pdf(ctx.config.TOPOLOGY_DOT, ctx.config.TOPOLOGY_PDF)
        if not ctx.pdf_generated:
            logger.warning("  ⚠ GraphViz not found — DOT file created, PDF skipped")
            logger.info(f"  → Install GraphViz, then run: sfdp -Tpdf {ctx.config.TOPOLOGY_DOT} -o {ctx.config.TOPOLOGY_PDF}")
