import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class AppDocumentationStep(PipelineStep):
    name        = "Per-Application Documentation"
    step_number = "12.1"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from generators.app_doc_generator import ApplicationDocGenerator

        output_dir = ctx.config.EXPORTS_DIR / "app_docs"
        gen = ApplicationDocGenerator(ctx.enriched_data)
        summary = gen.generate_all(output_dir)
        if summary.get("generated", 0) > 0:
            logger.info(f"  Generated {summary['generated']} per-application doc(s): {output_dir}")
        else:
            logger.warning("  ⚠ No per-application docs generated")
