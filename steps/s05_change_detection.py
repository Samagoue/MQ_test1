import logging
from datetime import datetime

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class ChangeDetectionStep(PipelineStep):
    name        = "Change Detection"
    step_number = "5"

    def should_run(self, ctx: PipelineContext) -> bool:
        return bool(ctx.enriched_data)

    def run(self, ctx: PipelineContext) -> None:
        from processors.change_detector import ChangeDetector, generate_html_report
        from utils.file_io import load_json, save_json

        baseline_file = ctx.config.BASELINE_JSON
        change_detection_success = True

        if baseline_file.exists():
            try:
                baseline_data = load_json(baseline_file)
                detector = ChangeDetector()
                ctx.changes = detector.compare(ctx.enriched_data, baseline_data)

                baseline_ts = baseline_file.stat().st_mtime
                ctx.baseline_time_str = datetime.fromtimestamp(baseline_ts).strftime("%Y-%m-%d %H:%M:%S")

                report_file = ctx.config.REPORTS_DIR / f"change_report_{ctx.timestamp}.html"
                generate_html_report(ctx.changes, report_file, ctx.timestamp, ctx.baseline_time_str)

                change_json = ctx.config.DATA_DIR / f"changes_{ctx.timestamp}.json"
                save_json(ctx.changes, change_json)

                logger.info(f"  Detected {ctx.changes['summary']['total_changes']} changes")
                logger.info(f"  Change report: {report_file}")
            except Exception as e:
                logger.warning(f"  ⚠ Change detection failed: {e}")
                logger.warning("  ⚠ Baseline will NOT be updated to preserve change detection capability")
                ctx.errors.append(f"Change detection: {e}")
                change_detection_success = False
        else:
            logger.warning("  No baseline found — this will be the first baseline")

        if change_detection_success:
            save_json(ctx.enriched_data, baseline_file)
            logger.info(f"  Baseline updated: {baseline_file}")
        else:
            logger.warning("  Baseline NOT updated due to change detection failure")
