"""
Cross-Country Asset Association — Confluence Page Generator

Produces a single Confluence wiki-markup page from asset_associations.json.

Page structure:
    1. Header panel (dark blue) with title, timestamp, and aggregate stats
    2. Metric cards — Countries | Channels | Associations
    3. h2. Country Index — summary table with status lozenge per country
    4. h2. Country Details — one {expand} block per country (A-Z):
           - channel highlighted in a light-blue panel
           - association table (source + target queue details)
           - {info} callout for countries with channel but no associations
    5. Footer panel (matches EA doc_generator style)

Status lozenge logic:
    ACTIVE (Green)       — channel found AND associations present
    CHANNEL ONLY (Yellow) — channel found, no queue associations
    QUEUES ONLY (Blue)   — associations present, no channel
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from utils.file_io import load_json, save_json
from utils.logging_config import get_logger

logger = get_logger("generators.association_doc_generator")


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

        # Pre-compute aggregate stats
        self._n_countries = len(self._data)
        self._n_channels = sum(1 for g in self._data if g.get("channel"))
        self._n_associations = sum(len(g.get("associations", [])) for g in self._data)

    # ── Public API ──────────────────────────────────────────────────────────

    def generate_confluence_markup(self, output_file: Path) -> bool:
        """Build the full page and write to output_file."""
        doc: List[str] = []
        doc.extend(self._header())
        doc.extend(self._metric_cards())
        doc.extend(self._index_table())
        doc.extend(self._country_details())
        doc.extend(self._footer())

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(doc))

        logger.info(f"✓ Asset Association documentation generated: {output_file}")
        return True

    # ── Section builders ────────────────────────────────────────────────────

    def _header(self) -> List[str]:
        return [
            "{panel:bgColor=#1e3a5f|borderColor=#1e3a5f|titleBGColor=#1e3a5f|titleColor=#ffffff"
            "|title=Cross-Country Asset Associations}",
            "",
            f"{{color:#ffffff}}*Generated:* {self._timestamp} | "
            f"*Countries:* {self._n_countries} | "
            f"*Channels:* {self._n_channels} | "
            f"*Associations:* {self._n_associations:,}{{color}}",
            "",
            "{panel}",
            "",
            "{toc}",
            "",
            "----",
            "",
        ]

    def _metric_cards(self) -> List[str]:
        lines = [
            "h2. Summary",
            "",
            "{section}",
            "{column:width=33%}",
            "{panel:bgColor=#e8f4f8|borderColor=#0077b6|title=Countries}",
            f"*{self._n_countries}*",
            "{panel}",
            "{column}",
            "{column:width=33%}",
            "{panel:bgColor=#e8f4f8|borderColor=#0077b6|title=Channels Identified}",
            f"*{self._n_channels}*",
            "{panel}",
            "{column}",
            "{column:width=33%}",
            "{panel:bgColor=#e8f4f8|borderColor=#0077b6|title=Queue Associations}",
            f"*{self._n_associations:,}*",
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
            "||Country||Channel||Associations||Status||",
        ]
        for group in self._data:
            country = group.get("Country", "")
            channel = group.get("channel", "")
            count = len(group.get("associations", []))

            if channel and count:
                status = "{status:colour=Green|title=ACTIVE}"
            elif channel:
                status = "{status:colour=Yellow|title=CHANNEL ONLY}"
            else:
                status = "{status:colour=Blue|title=QUEUES ONLY}"

            lines.append(f"|{country}|{channel or '—'}|{count}|{status}|")

        lines.append("")
        return lines

    def _country_details(self) -> List[str]:
        lines = [
            "h2. Country Details",
            "",
        ]
        for group in self._data:
            country = group.get("Country", "")
            channel = group.get("channel", "")
            assocs = group.get("associations", [])
            count = len(assocs)

            plural = "s" if count != 1 else ""
            if channel:
                expand_title = (
                    f"{country} \u2014 {channel} ({count} association{plural})"
                )
            else:
                expand_title = f"{country} \u2014 no channel ({count} association{plural})"

            lines.append(f"{{expand:title={expand_title}}}")

            # Channel panel
            if channel:
                lines += [
                    "{panel:bgColor=#e3f2fd|borderColor=#90caf9"
                    "|titleBGColor=#1565c0|titleColor=#ffffff|title=Channel}",
                    f"*{channel}*",
                    "{panel}",
                    "",
                ]

            # Associations table or info callout
            if assocs:
                lines.append(
                    "||MQ Host||MQ Manager||Asset||Type|| ||"
                    "Target Host||Target Manager||Target Asset||Target Type||"
                )
                for a in assocs:
                    lines.append(
                        f"|{a.get('MQ_host','')}|{a.get('MQmanager','')}|"
                        f"{a.get('asset','')}|{a.get('asset_type','')}| |"
                        f"{a.get('Target_MQ_host','')}|{a.get('Target_MQmanager','')}|"
                        f"{a.get('Target_asset','')}|{a.get('Target_asset_type','')}|"
                    )
            else:
                lines.append(
                    "{info}Channel identified but no queue associations matched "
                    "for this country.{info}"
                )

            lines.append("{expand}")
            lines.append("")

        return lines

    def _footer(self) -> List[str]:
        return [
            "----",
            "{panel:bgColor=#f0f0f0}",
            f"_Auto-generated by MQ CMDB Pipeline on {self._timestamp}_",
            "",
            "*Document Type:* Cross-Country Asset Association | "
            "*Classification:* Internal",
            "{panel}",
        ]
