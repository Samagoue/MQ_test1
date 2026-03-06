import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class ConvertJsonStep(PipelineStep):
    name        = "Convert to JSON Structure"
    step_number = "3"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.directorate_data)

    def run(self, ctx: PipelineContext) -> None:
        from processors.mqmanager_processor import MQManagerProcessor
        processor = MQManagerProcessor(ctx.raw_data, ctx.config.FIELD_MAPPINGS)
        ctx.directorate_data = processor.convert_to_json(ctx.directorate_data)
