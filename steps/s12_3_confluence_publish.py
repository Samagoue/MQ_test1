import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class ConfluencePublishStep(PipelineStep):
    name        = "Confluence Publishing"
    step_number = "12.3"

    def should_run(self, ctx: PipelineContext) -> bool:
        return getattr(ctx.config, "ENABLE_CONFLUENCE_PUBLISH", False)

    def run(self, ctx: PipelineContext) -> None:
        from utils.confluence_shim import (
            is_configured, attach_diagrams_enabled, app_docs_enabled,
            publish_ea_documentation, publish_application_diagrams,
            publish_app_documentation, publish_consolidated_report,
        )

        if not is_configured():
            logger.info("  Confluence not configured — skipping publish")
            logger.info("  → Configure config/confluence_config.json to enable")
            return

        # Publish EA documentation markup page
        if ctx.ea_doc_file and ctx.ea_doc_file.exists():
            result = publish_ea_documentation(
                doc_file=str(ctx.ea_doc_file),
                version_comment=f"Pipeline run {ctx.timestamp}",
            )
            if result:
                logger.info(f"  EA documentation published (page {result.get('id', 'N/A')})")
            else:
                logger.warning("  ⚠ EA documentation publish returned no result")
                ctx.errors.append("Confluence: EA doc publish returned no result")
        else:
            logger.warning("  ⚠ No EA documentation file to publish")

        # Publish per-application documentation pages
        app_doc_result = {}
        if app_docs_enabled():
            app_doc_result = publish_app_documentation(
                enriched_data=ctx.enriched_data,
                version_comment=f"Pipeline run {ctx.timestamp}",
            )
            if app_doc_result.get("published", 0) > 0:
                logger.info(f"  Published {app_doc_result['published']} per-app doc(s) to Confluence")
            if app_doc_result.get("errors", 0) > 0:
                logger.warning(f"  ⚠ {app_doc_result['errors']} per-app doc(s) failed to publish")
                ctx.errors.append(f"Confluence: {app_doc_result['errors']} per-app doc(s) failed")

        # Attach application diagram SVGs to per-app pages
        if attach_diagrams_enabled():
            page_map = app_doc_result.get("page_map", {})
            diagram_summary = publish_application_diagrams(
                comment=f"Pipeline run {ctx.timestamp}",
                page_map=page_map,
            )
            if diagram_summary.get("attached", 0) > 0:
                logger.info(f"  Attached {diagram_summary['attached']} diagram(s) to Confluence")
            if diagram_summary.get("errors", 0) > 0:
                logger.warning(f"  ⚠ {diagram_summary['errors']} diagram attachment(s) failed")
                ctx.errors.append(f"Confluence: {diagram_summary['errors']} diagram attachment(s) failed")

        # Attach consolidated report
        if ctx.consolidated_report_file and ctx.consolidated_report_file.exists():
            pub_ok = publish_consolidated_report(
                ctx.consolidated_report_file,
                version_comment=f"Pipeline run {ctx.timestamp}",
            )
            if pub_ok:
                logger.info("  Consolidated report published to Confluence")
            else:
                logger.warning("  ⚠ Consolidated report attachment failed")
                ctx.errors.append("Confluence: consolidated report attachment failed")
