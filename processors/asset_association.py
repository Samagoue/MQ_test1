"""Asset Association Processor — cross-country pattern-based asset mapping.

Two complementary matching passes are run and their results joined by country:

Pass 1 — JSON patterns (patterns.json, parallel)
    SOURCE → TARGET pairs with $$/$$$  country-code substitution.
    Each match emits a flat association record (source queue + resolved target).

Pass 2 — Built-in patterns (hardcoded in BUILTIN_PATTERNS, sequential)
    Source-only patterns not in patterns.json.
    Currently: ORG_AP_COUNTRY$$ → identifies the per-country channel.

Join + group step
    Records are grouped by country in the output.  Because one country maps to
    one channel but many queue associations (many-to-many), the channel appears
    once per country group and the associations are listed under it:

        [
          {
            "Country": "United Kingdom",
            "channel": "ORG_AP_COUNTRYUK",
            "associations": [
              {
                "MQ_host": ..., "MQmanager": ...,
                "asset": ..., "asset_type": ...,
                "Target_MQ_host": ..., "Target_MQmanager": ...,
                "Target_asset": ..., "Target_asset_type": ...
              },
              ...               <- many-to-many rows, channel not repeated
            ]
          },
          ...
        ]

    Countries with a channel but no pattern-matched associations still appear
    with an empty associations list so every channel is visible.

Output is written to Config.ASSET_ASSOCIATIONS_JSON, sorted by country name.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from typing import Dict, List, Tuple

from utils.file_io import load_json, save_json

logger = logging.getLogger(__name__)

# ── Built-in source patterns (not in patterns.json) ────────────────────────
# Each entry: (source_template, asset_type_override)
# $$ = two-char country code,  $$$ = three-char country code
BUILTIN_PATTERNS: List[Tuple[str, str]] = [
    ("ORG_AP_COUNTRY$$", "channel"),
]

# ── Worker-process globals (populated once per worker by Pool initializer) ──
_mq_lookup: Dict[str, Tuple[str, str, str]] = {}
_patterns:  List[Tuple[str, str]] = []
_countries: List[Dict] = []


def _init_worker(mq_lkp, pat, cty):
    global _mq_lookup, _patterns, _countries
    _mq_lookup = mq_lkp
    _patterns  = pat
    _countries = cty


def _process_asset(row: Dict) -> Tuple[List[Dict], int, int]:
    """Resolve all JSON-pattern-matched targets for a single source asset row."""
    src_asset = row.get("asset", "").strip()
    if not src_asset:
        return [], 0, 1

    src_upper = src_asset.upper()
    output: List[Dict] = []
    matched = False

    for src_pattern, trg_pattern in _patterns:
        for c in _countries:
            test_src = (
                src_pattern
                .replace("$$$", c["three"])
                .replace("$$",  c["two"])
            )
            if test_src != src_upper:
                continue

            trg_asset = (
                trg_pattern
                .replace("$$$", c["three"])
                .replace("$$",  c["two"])
            )
            trg_info = _mq_lookup.get(trg_asset.upper())
            if trg_info:
                trg_host, trg_mgr, trg_type = trg_info
                output.append({
                    "Country":           c["name"],
                    "MQ_host":           row.get("MQ_host", ""),
                    "MQmanager":         row.get("MQmanager", ""),
                    "asset":             src_asset,
                    "asset_type":        row.get("asset_type", ""),
                    "Target_MQ_host":    trg_host,
                    "Target_MQmanager":  trg_mgr,
                    "Target_asset":      trg_asset,
                    "Target_asset_type": trg_type,
                })
                matched = True

    return output, len(output), 0 if matched else 1


def _scan_builtin_patterns(
    raw_data: List[Dict],
    countries: List[Dict],
) -> Dict[str, str]:
    """Scan raw_data for hardcoded source patterns to build country → channel map.

    Returns:
        Dict mapping country_name → channel asset name.
        One channel per country (last match wins if duplicates exist).
    """
    channel_map: Dict[str, str] = {}

    for row in raw_data:
        src_asset = row.get("asset", "").strip()
        if not src_asset:
            continue
        src_upper = src_asset.upper()

        for src_template, _ in BUILTIN_PATTERNS:
            for c in countries:
                test_src = (
                    src_template
                    .replace("$$$", c["three"])
                    .replace("$$",  c["two"])
                )
                if test_src == src_upper:
                    channel_map[c["name"]] = src_asset
                    break   # one country per asset — move to next asset

    return channel_map


def _group_by_country(
    flat_records: List[Dict],
    country_channel_map: Dict[str, str],
) -> List[Dict]:
    """Group flat association records by country.

    Each country entry contains:
        Country      — country name
        channel      — from country_channel_map (empty string if none found)
        associations — list of {MQ_host, MQmanager, asset, asset_type,
                                Target_MQ_host, Target_MQmanager,
                                Target_asset, Target_asset_type}

    Countries that have a channel but no associations still appear with an
    empty associations list.
    """
    buckets: Dict[str, List[Dict]] = defaultdict(list)
    for rec in flat_records:
        country = rec["Country"]
        buckets[country].append({
            "MQ_host":           rec["MQ_host"],
            "MQmanager":         rec["MQmanager"],
            "asset":             rec["asset"],
            "asset_type":        rec["asset_type"],
            "Target_MQ_host":    rec["Target_MQ_host"],
            "Target_MQmanager":  rec["Target_MQmanager"],
            "Target_asset":      rec["Target_asset"],
            "Target_asset_type": rec["Target_asset_type"],
        })

    all_countries = sorted(set(buckets) | set(country_channel_map))

    return [
        {
            "Country":      country,
            "channel":      country_channel_map.get(country, ""),
            "associations": buckets.get(country, []),
        }
        for country in all_countries
    ]


def run(raw_data: List[Dict], config, _logger=None) -> None:
    """Run asset association — entry point for the monolith orchestrator.

    Args:
        raw_data: List of raw MQ asset records (from all_MQCMDB_assets.json).
        config:   Config class (config.settings.Config).
        _logger:  Optional logger; falls back to module logger if not provided.
    """
    log = _logger or logger

    patterns_path = config.PATTERNS_JSON
    country_path  = config.COUNTRY_CODE_JSON
    output_path   = config.ASSET_ASSOCIATIONS_JSON

    if not country_path.exists():
        log.info(f"  Skipped: {country_path.name} not found in input/")
        return

    start = time.time()

    cty_raw = load_json(country_path)
    cty = [
        {
            "name":  row["country_name"].strip(),
            "two":   row["two_char"].strip().upper(),
            "three": row["three_char"].strip().upper(),
        }
        for row in cty_raw
        if row.get("two_char") and row.get("three_char") and row.get("country_name")
    ]

    # Pass 2 first: build country → channel map
    country_channel_map = _scan_builtin_patterns(raw_data, cty)
    log.info(f"  Pass 2 (built-in): {len(country_channel_map)} channel(s) identified")

    flat_records: List[Dict] = []
    total_skipped = 0

    if patterns_path.exists():
        mq_lkp: Dict[str, Tuple[str, str, str]] = {
            row["asset"].upper(): (
                row.get("MQ_host", ""),
                row.get("MQmanager", ""),
                row.get("asset_type", ""),
            )
            for row in raw_data
            if row.get("asset")
        }

        pat_raw = load_json(patterns_path)
        pat = [
            (row["SOURCE"].strip().upper(), row["TARGET"].strip())
            for row in pat_raw
            if row.get("SOURCE") and row.get("TARGET")
        ]

        log.info(
            f"  Pass 1 (JSON patterns): {len(pat)} patterns × "
            f"{len(cty)} countries × {len(raw_data):,} assets"
        )

        workers = max(cpu_count() - 1, 1)
        with Pool(
            processes=workers,
            initializer=_init_worker,
            initargs=(mq_lkp, pat, cty),
        ) as pool:
            results = pool.map(_process_asset, raw_data)

        for rows, _, skip in results:
            flat_records.extend(rows)
            total_skipped += skip
    else:
        log.info(f"  Pass 1 skipped: {patterns_path.name} not found in input/")

    grouped = _group_by_country(flat_records, country_channel_map)
    total_assoc = sum(len(g["associations"]) for g in grouped)
    save_json(grouped, output_path)

    elapsed = round(time.time() - start, 2)
    log.info(
        f"  {len(grouped)} countries | {total_assoc:,} associations | "
        f"{total_skipped:,} unmatched → {output_path.name} ({elapsed}s)"
    )
