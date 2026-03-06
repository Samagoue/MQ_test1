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

        # Build host→directorate map
        if ctx.config.HOSTS_JSON.exists():
            hosts_data = load_json(ctx.config.HOSTS_JSON)
            for h in hosts_data:
                hostname = str(h.get("hostname", "")).strip()
                host_dir = str(h.get("host_directorate", "")).strip()
                if hostname and host_dir:
                    ctx.host_directorate_map[hostname.upper()] = host_dir
            logger.info(f"  Host→directorate map: {len(ctx.host_directorate_map)} entries")
        else:
            logger.warning("  ⚠ all_cmdb_hosts.json not found — QM directorate will use asset-level fallback")

        # Load MQ Manager aliases
        if ctx.config.MQMANAGER_ALIASES_JSON.exists():
            aliases_data = load_json(ctx.config.MQMANAGER_ALIASES_JSON)
            for entry in aliases_data:
                canonical = str(entry.get("canonical", "")).strip()
                for alias in entry.get("aliases", []):
                    alias = str(alias).strip()
                    if alias and canonical:
                        ctx.alias_to_canonical[alias.upper()] = canonical
            logger.info(f"  Alias map: {len(ctx.alias_to_canonical)} alias(es) loaded")
        else:
            logger.info("  No mqmanager_aliases.json found — alias resolution skipped")
