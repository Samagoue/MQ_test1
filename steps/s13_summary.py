import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class SummaryStep(PipelineStep):
    name        = "Pipeline Summary"
    step_number = "13"

    def run(self, ctx: PipelineContext) -> None:
        ctx.summary_stats = _calculate_summary(ctx.enriched_data)
        _print_summary(ctx.summary_stats, ctx.errors)


def _calculate_summary(enriched_data: dict) -> dict:
    stats = {
        "Organizations":   len(enriched_data),
        "Departments":     0,
        "Business Owners": 0,
        "Applications":    0,
        "MQ Managers":     0,
        "Total QLocal":    0,
        "Total QRemote":   0,
        "Total QAlias":    0,
        "Total Connections": 0,
    }
    for org_data in enriched_data.values():
        departments = org_data.get("_departments", {})
        stats["Departments"] += len(departments)
        for biz_owners in departments.values():
            stats["Business Owners"] += len(biz_owners)
            for applications in biz_owners.values():
                stats["Applications"] += len(applications)
                for mqmanagers in applications.values():
                    stats["MQ Managers"] += len(mqmanagers)
                    for mq_data in mqmanagers.values():
                        stats["Total QLocal"]  += mq_data.get("qlocal_count", 0)
                        stats["Total QRemote"] += mq_data.get("qremote_count", 0)
                        stats["Total QAlias"]  += mq_data.get("qalias_count", 0)
                        stats["Total Connections"] += len(mq_data.get("outbound", []))
    return stats


def _print_summary(stats: dict, errors: list) -> None:
    logger.info("\n" + "-" * 70)
    logger.info("SUMMARY STATISTICS")
    logger.info("-" * 70)
    for key, value in stats.items():
        logger.info(f"{key + ':':21} {value}")
    logger.info("-" * 70)
    if errors:
        logger.warning("\nWarnings during execution:")
        for error in errors:
            logger.info(f"  ⚠ {error}")
