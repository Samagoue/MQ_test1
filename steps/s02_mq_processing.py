import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class MQProcessingStep(PipelineStep):
    name        = "Process MQ Manager Relationships"
    step_number = "2"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.raw_data)

    def run(self, ctx: PipelineContext) -> None:
        from processors.mqmanager_processor import MQManagerProcessor
        processor = MQManagerProcessor(ctx.raw_data, ctx.config.FIELD_MAPPINGS)
        ctx.directorate_data = processor.process_assets()
        processor.print_stats()
        # Preserve augmentation records for step 10.5
        ctx.augmentation_records = getattr(processor, "augmentation_records", [])
