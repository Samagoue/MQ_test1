import logging
from pathlib import Path

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class ConsolidatedReportStep(PipelineStep):
    name        = "Consolidated Report"
    step_number = "10.5"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from utils.report_consolidator import generate_consolidated_report
        from utils.file_io import load_json, save_json

        consolidated_file = ctx.config.REPORTS_DIR / f"consolidated_report_{ctx.timestamp}.html"

        # Merge augmentation records with user-maintained file
        augmentation_data = None
        augmentation_file = ctx.config.INPUT_DIR / "data_augmentation.json"
        try:
            augmentation_data = _merge_augmentation(
                ctx.augmentation_records, augmentation_file
            )
            if augmentation_data:
                logger.info(f"  Data augmentation: {len(augmentation_data)} records")
        except Exception as e:
            logger.warning(f"  ⚠ Data augmentation generation failed: {e}")

        generate_consolidated_report(
            changes=ctx.changes,
            gateway_analytics=ctx.gateway_analytics,
            output_file=consolidated_file,
            current_timestamp=ctx.timestamp,
            baseline_timestamp=ctx.baseline_time_str,
        )
        ctx.consolidated_report_file = consolidated_file
        logger.info(f"  Consolidated report: {consolidated_file}")


def _merge_augmentation(extracted: list, augmentation_file: Path) -> list:
    """Merge processor-captured augmentation records with user-maintained JSON."""
    from utils.file_io import load_json, save_json

    existing = []
    if augmentation_file.exists():
        try:
            existing = load_json(augmentation_file) or []
        except Exception:
            existing = []

    existing_keys = {
        (r.get("field_name", ""), r.get("MQmanager", "")) for r in existing
    }

    new_count = 0
    for record in extracted:
        key = (record["field_name"], record["MQmanager"])
        if key not in existing_keys:
            record["Application"] = ""
            record["Org"] = ""
            record["Validity"] = ""
            existing.append(record)
            existing_keys.add(key)
            new_count += 1

    save_json(existing, augmentation_file)
    if new_count > 0:
        logger.info(f"  Added {new_count} new entries to {augmentation_file}")

    return existing
