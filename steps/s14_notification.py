import logging
import os

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class NotificationStep(PipelineStep):
    name        = "Email Notification"
    step_number = "14"

    # Populated by orchestrator before calling run()
    success: bool = True
    error_message: str = None

    def should_run(self, ctx: PipelineContext) -> bool:
        return os.environ.get("EMAIL_ENABLED", "").lower() in ("true", "1", "yes")

    def run(self, ctx: PipelineContext) -> None:
        from utils.email_notifier import get_notifier

        notifier = get_notifier()
        if not notifier.is_enabled:
            logger.warning("  ⚠ Email notifications not configured")
            return

        summary = dict(ctx.summary_stats)
        err_msg = self.error_message
        if ctx.errors:
            summary["Warnings"] = len(ctx.errors)
            details = "\n".join(f"  - {e}" for e in ctx.errors)
            err_msg = f"{err_msg}\n\nWarnings:\n{details}" if err_msg else f"Warnings during execution:\n{details}"

        result = notifier.send_pipeline_notification(
            success=self.success,
            summary=summary,
            error_message=err_msg,
            report_file=ctx.consolidated_report_file,
        )
        if result:
            logger.info("  Email notification sent")
        else:
            logger.warning("  ⚠ Failed to send email notification")
            for err in notifier.errors:
                logger.info(f"  - {err}")
