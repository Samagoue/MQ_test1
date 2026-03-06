import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class MultiFormatExportStep(PipelineStep):
    name        = "Multi-Format Exports"
    step_number = "11"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from utils.export_formats import (
            export_directory_to_formats,
            export_dot_to_png,
            export_dot_to_svg,
            generate_excel_inventory,
        )

        if ctx.config.TOPOLOGY_DOT.exists():
            export_dot_to_svg(ctx.config.TOPOLOGY_DOT, ctx.config.TOPOLOGY_DIR / "mq_topology.svg")
            export_dot_to_png(ctx.config.TOPOLOGY_DOT, ctx.config.TOPOLOGY_DIR / "mq_topology.png", dpi=200)

        if ctx.config.APPLICATION_DIAGRAMS_DIR.exists():
            export_directory_to_formats(ctx.config.APPLICATION_DIAGRAMS_DIR, formats=["svg"], dpi=150)

        if ctx.config.INDIVIDUAL_DIAGRAMS_DIR.exists():
            export_directory_to_formats(ctx.config.INDIVIDUAL_DIAGRAMS_DIR, formats=["svg"], dpi=150)

        excel_file = ctx.config.EXPORTS_DIR / f"mqcmdb_inventory_{ctx.timestamp}.xlsx"
        if generate_excel_inventory(ctx.enriched_data, excel_file):
            logger.info(f"  Excel inventory: {excel_file}")
