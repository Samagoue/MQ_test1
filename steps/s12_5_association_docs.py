import logging

from core.interfaces import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class AssetAssociationDocStep(PipelineStep):
    name        = "Asset Association Documentation"
    step_number = "12.5"

    def should_run(self, ctx: PipelineContext) -> bool:
        return ctx.config.ASSET_ASSOCIATIONS_JSON.exists()

    def run(self, ctx: PipelineContext) -> None:
        from generators.association_doc_generator import AssociationDocGenerator

        out = ctx.config.EXPORTS_DIR / f"Asset_Associations_{ctx.timestamp}.txt"
        AssociationDocGenerator(ctx.config.ASSET_ASSOCIATIONS_JSON).generate(out)
        logger.info(f"  Asset Association doc: {out}")

        try:
            from utils.confluence_shim import publish_asset_association_doc
            published = publish_asset_association_doc(out, ctx.timestamp)
            if not published:
                logger.info("  → Import manually into Confluence using Insert → Markup")
        except Exception as pub_e:
            logger.warning(f"  ⚠ Confluence publish skipped: {pub_e}")
            logger.info("  → Import manually into Confluence using Insert → Markup")
