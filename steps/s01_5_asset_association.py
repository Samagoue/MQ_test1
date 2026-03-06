import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class AssetAssociationStep(PipelineStep):
    name        = "Asset Association"
    step_number = "1.5"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.raw_data)

    def run(self, ctx: PipelineContext) -> None:
        from processors.asset_association import run as run_assoc
        run_assoc(ctx.raw_data, ctx.config, logger)
