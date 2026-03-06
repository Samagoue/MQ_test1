import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class LoadDataStep(PipelineStep):
    name        = "Load MQ CMDB Data"
    step_number = "1"

    def should_run(self, ctx: PipelineContext) -> bool:
        return not ctx.skip_export

    def run(self, ctx: PipelineContext) -> None:
        from utils.file_io import load_json
        ctx.raw_data = load_json(ctx.config.INPUT_JSON)
        logger.info(f"  Loaded {len(ctx.raw_data):,} records")
