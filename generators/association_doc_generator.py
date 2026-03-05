"""
Cross-Country Asset Association — Confluence Page Generator

Produces a single Confluence wiki-markup page from asset_associations.json.

Page structure:
    1. Hero header (deep indigo) with title, subtitle, and live stats bar
    2. Intro info panel explaining the page
    3. Metric cards — Countries (blue) | Channels (teal) | Associations (orange)
    4. h2. Country Index — summary table with status lozenges
    5. h2. Country Details — one {expand} per country (A-Z):
           - channel highlighted in a branded panel
           - source → target association table with clear column grouping
           - {note} callout for channel-only countries (no associations yet)
    6. Document Information footer (matches EA doc_generator style)

Status lozenge logic:
    ACTIVE       (Green)  — channel found AND associations present
    CHANNEL ONLY (Yellow) — channel found, no queue associations
    QUEUES ONLY  (Blue)   — associations present, no channel
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from utils.file_io import load_json
from utils.logging_config import get_logger

logger = get_logger("generators.association_doc_generator")

# ── Color palette ────────────────────────────────────────────────────────────
_C = {
    # Header
    "hero_bg":        "#1a237e",   # deep indigo
    "hero_border":    "#1a237e",
    "hero_title_bg":  "#283593",
    "hero_title_fg":  "#ffffff",
    # Metric cards
    "card_countries_bg":    "#e3f2fd",
    "card_countries_hdr":   "#1565c0",
    "card_channels_bg":     "#e8f5e9",
    "card_channels_hdr":    "#2e7d32",
    "card_assoc_bg":        "#fff3e0",
    "card_assoc_hdr":       "#e65100",
    # Channel panel inside expand
    "ch_bg":          "#ede7f6",
    "ch_border":      "#b39ddb",
    "ch_title_bg":    "#4527a0",
    "ch_title_fg":    "#ffffff",
    # Source / target sub-headers in table (color-coded text)
    "src_color":      "#1565c0",   # blue
    "tgt_color":      "#2e7d32",   # green
    # Footer
    "footer_bg":      "#eceff1",
    "footer_border":  "#90a4ae",
    "footer_title_bg":"#37474f",
    "footer_title_fg":"#ffffff",
}


class AssociationDocGenerator:
    """Generate Confluence markup for the cross-country asset association page."""

    def __init__(self, associations_file: Path):
        """
        Load and validate the associations JSON produced by asset_association.run().

        Args:
            associations_file: Path to asset_associations.json
        """
        raw = load_json(associations_file)
        if not isinstance(raw, list):
            raise ValueError(
                f"Expected a list in {associations_file}, got {type(raw).__name__}"
            )
        self._data: List[Dict] = raw
        self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._date_only  = datetime.now().strftime("%d %B %Y")

        # Aggregate stats
        self._n_countries    = len(self._data)
        self._n_channels     = sum(1 for g in self._data if g.get("channel"))
        self._n_associations = sum(len(g.get("associations", [])) for g in self._data)
        self._n_active       = sum(
            1 for g in self._data
            if g.get("channel") and g.get("associations")
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def generate_confluence_markup(self, output_file: Path) -> bool:
        """Build the full page and write to output_file."""
        doc: List[str] = []
        doc.extend(self._hero_header())
        doc.extend(self._intro_panel())
        doc.extend(self._metric_cards())
        doc.extend(self._index_table())
        doc.extend(self._country_details())
        doc.extend(self._footer())

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(doc))

        logger.info(f"✓ Asset Association documentation generated: {output_file}")
        return True

    # ── Section builders ─────────────────────────────────────────────────────

    def _hero_header(self) -> List[str]:
        c = _C
        return [
            f"{{panel:bgColor={c['hero_bg']}|borderColor={c['hero_border']}"
            f"|titleBGColor={c['hero_title_bg']}|titleColor={c['hero_title_fg']}"
            f"|title=IBM MQ CMDB  |  Cross-Country Asset Associations}}",
            "",
            f"{{color:#ffffff}}*Cross-Country Asset Associations*{{color}}",
            f"{{color:#90caf9}}Mapping source queues to their cross-country targets"
            f" via country-code pattern substitution{{color}}",
            "",
            f"{{color:#bbdefb}}*Generated:* {self._timestamp}"
            f"  |  *Countries:* {self._n_countries}"
            f"  |  *Channels:* {self._n_channels}"
            f"  |  *Active:* {self._n_active}"
            f"  |  *Associations:* {self._n_associations:,}{{color}}",
            "",
            "{panel}",
            "",
            "{toc:maxLevel=2}",
            "",
            "----",
            "",
        ]

    def _intro_panel(self) -> List[str]:
        return [
            "{info:title=About This Page}",
            "This page presents the *cross-country asset association* analysis for the IBM MQ CMDB estate.",
            "Each country group shows:",
            "* *Channel* — the per-country ORG_AP_COUNTRY channel asset identified for that country",
            "* *Associations* — source queue \u2192 target queue pairs matched via pattern substitution",
            "",
            "Use the *Country Index* below for a quick overview, then expand any country to drill into its full queue mapping.",
            "{info}",
            "",
        ]

    def _metric_cards(self) -> List[str]:
        c = _C
        coverage_pct = (
            round(self._n_channels / self._n_countries * 100)
            if self._n_countries else 0
        )
        avg_assoc = (
            round(self._n_associations / max(self._n_active, 1), 1)
        )
        lines = [
            "h2. Summary",
            "",
            "{section}",

            # Card 1 — Countries
            "{column:width=33%}",
            f"{{panel:bgColor={c['card_countries_bg']}|borderColor={c['card_countries_hdr']}"
            f"|titleBGColor={c['card_countries_hdr']}|titleColor=#ffffff|title=Countries}}",
            f"{{color:{c['card_countries_hdr']}}}*{self._n_countries}*{{color}}",
            f"{{color:#555555}}_Channel coverage: {coverage_pct}%_{{color}}",
            "{panel}",
            "{column}",

            # Card 2 — Channels
            "{column:width=33%}",
            f"{{panel:bgColor={c['card_channels_bg']}|borderColor={c['card_channels_hdr']}"
            f"|titleBGColor={c['card_channels_hdr']}|titleColor=#ffffff|title=Channels Identified}}",
            f"{{color:{c['card_channels_hdr']}}}*{self._n_channels}*{{color}}",
            f"{{color:#555555}}_Active: {self._n_active} countries_{{color}}",
            "{panel}",
            "{column}",

            # Card 3 — Associations
            "{column:width=33%}",
            f"{{panel:bgColor={c['card_assoc_bg']}|borderColor={c['card_assoc_hdr']}"
            f"|titleBGColor={c['card_assoc_hdr']}|titleColor=#ffffff|title=Queue Associations}}",
            f"{{color:{c['card_assoc_hdr']}}}*{self._n_associations:,}*{{color}}",
            f"{{color:#555555}}_Avg {avg_assoc} per active country_{{color}}",
            "{panel}",
            "{column}",

            "{section}",
            "",
        ]
        return lines

    def _index_table(self) -> List[str]:
        lines = [
            "h2. Country Index",
            "",
            "||  ||Country||Channel||Associations||Status||",
        ]
        for i, group in enumerate(self._data, start=1):
            country  = group.get("Country", "")
            channel  = group.get("channel", "")
            count    = len(group.get("associations", []))

            if channel and count:
                status = "{status:colour=Green|title=ACTIVE}"
            elif channel:
                status = "{status:colour=Yellow|title=CHANNEL ONLY}"
            else:
                status = "{status:colour=Blue|title=QUEUES ONLY}"

            # Row number in grey for easy scanning
            row_num = f"{{color:#999999}}{i}{{color}}"
            lines.append(
                f"|{row_num}|*{country}*|{{color:#555555}}{channel or '\u2014'}{{color}}"
                f"|{count}|{status}|"
            )

        lines += ["", "----", ""]
        return lines

    def _country_details(self) -> List[str]:
        c = _C
        lines = ["h2. Country Details", ""]

        for group in self._data:
            country = group.get("Country", "")
            channel = group.get("channel", "")
            assocs  = group.get("associations", [])
            count   = len(assocs)

            # Status badge in the expand title for at-a-glance scanning
            plural = "s" if count != 1 else ""
            if channel and count:
                badge = "ACTIVE"
                count_str = f"{count} association{plural}"
            elif channel:
                badge = "CHANNEL ONLY"
                count_str = "no associations yet"
            else:
                badge = "QUEUES ONLY"
                count_str = f"{count} association{plural}"

            expand_title = (
                f"{country}  [{badge}]"
                f"  \u2014  {channel or 'no channel'}"
                f"  ({count_str})"
            )
            lines.append(f"{{expand:title={expand_title}}}")

            # ── Channel panel ───────────────────────────────────────────────
            if channel:
                lines += [
                    f"{{panel:bgColor={c['ch_bg']}|borderColor={c['ch_border']}"
                    f"|titleBGColor={c['ch_title_bg']}|titleColor={c['ch_title_fg']}"
                    f"|title=Channel Identifier}}",
                    f"{{color:{c['ch_title_bg']}}}*{channel}*{{color}}",
                    "{panel}",
                    "",
                ]
            else:
                lines += [
                    "{note:title=No Channel Found}",
                    "No ORG_AP_COUNTRY channel asset was identified for this country in the CMDB.",
                    "{note}",
                    "",
                ]

            # ── Associations ─────────────────────────────────────────────────
            if assocs:
                # Visual sub-heading for the table
                lines += [
                    f"{{color:{c['src_color']}}}*Source*{{color}}"
                    f" {{color:#999999}}\u2192{{color}}"
                    f" {{color:{c['tgt_color']}}}*Target*{{color}}",
                    "",
                    # Column headers — source group / arrow / target group
                    f"||{{color:{c['src_color']}}}Source MQ Host{{color}}"
                    f"||{{color:{c['src_color']}}}Source Manager{{color}}"
                    f"||{{color:{c['src_color']}}}Asset{{color}}"
                    f"||{{color:{c['src_color']}}}Type{{color}}"
                    f"|| ||"
                    f"{{color:{c['tgt_color']}}}Target MQ Host{{color}}"
                    f"||{{color:{c['tgt_color']}}}Target Manager{{color}}"
                    f"||{{color:{c['tgt_color']}}}Target Asset{{color}}"
                    f"||{{color:{c['tgt_color']}}}Target Type{{color}}||",
                ]
                for a in assocs:
                    lines.append(
                        f"|{a.get('MQ_host','')}|{a.get('MQmanager','')}|"
                        f"*{a.get('asset','')}*|{{color:#777777}}{a.get('asset_type','')}{{color}}|"
                        f"{{color:#aaaaaa}}\u2192{{color}}|"
                        f"{a.get('Target_MQ_host','')}|{a.get('Target_MQmanager','')}|"
                        f"*{a.get('Target_asset','')}*|"
                        f"{{color:#777777}}{a.get('Target_asset_type','')}{{color}}|"
                    )
            else:
                lines += [
                    "{note:title=No Queue Associations}",
                    "Channel identified but no queue associations matched for this country via the current patterns.",
                    "_Check_ {{patterns.json}} _to add cross-country source \u2192 target mappings._",
                    "{note}",
                ]

            lines += ["{expand}", ""]

        return lines

    def _footer(self) -> List[str]:
        c = _C
        return [
            "----",
            f"{{panel:bgColor={c['footer_bg']}|borderColor={c['footer_border']}"
            f"|titleBGColor={c['footer_title_bg']}|titleColor={c['footer_title_fg']}"
            f"|title=Document Information}}",
            f"_Generated by MQ CMDB Hierarchical Automation Pipeline on {self._timestamp}_",
            "",
            f"*Document:* Cross-Country Asset Associations"
            f"  |  *Date:* {self._date_only}"
            f"  |  *Classification:* Internal Use Only",
            "",
            f"{{status:colour=Green|title=ACTIVE}} channel + associations"
            f"  {{status:colour=Yellow|title=CHANNEL ONLY}} channel identified, no queue patterns matched"
            f"  {{status:colour=Blue|title=QUEUES ONLY}} associations present, no channel found",
            "{panel}",
        ]
