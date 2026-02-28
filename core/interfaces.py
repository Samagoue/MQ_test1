"""
Pipeline interfaces — Abstract Base Classes and shared data container.

This module defines the contracts that all pipeline components must satisfy.
The design goal is the Open/Closed Principle:

    Open for extension  — drop a new .py file into processors/, generators/,
                          analytics/, or utils/ and it runs automatically.
    Closed for modification — orchestrator.py never needs to change.

Component roles
---------------
    Processor  — transform raw/intermediate data into a structured form
    Generator  — produce output files (DOT, HTML, Excel, DOC, etc.)
    Analyzer   — produce analytics dicts stored on the shared context
    Publisher  — push outputs to external systems (Confluence, SharePoint…)
    Notifier   — send notifications (email, Slack, PagerDuty…)

Every component implements exactly one method:
    execute(context: PipelineContext) -> None

All shared state flows through PipelineContext, which is passed to every
step. This replaces the tangle of local variables in the original orchestrator
and makes it trivial to inspect what any step produced.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Shared data container
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PipelineContext:
    """Shared data bag passed through every pipeline step.

    Components read what they need from this object and write their results
    back to it. Fields are grouped by the pipeline phase that populates them.

    All fields default to None / empty so individual steps can be unit-tested
    in isolation without running the full pipeline from the beginning.
    """

    # ── Phase 1: raw inputs loaded from disk ──────────────────────────────
    raw_data:             Optional[List[Dict]] = None
    # Hostname → owning directorate (from all_cmdb_hosts.json)
    host_directorate_map: Dict[str, str] = field(default_factory=dict)
    # MQ Manager alias → canonical name
    alias_to_canonical:   Dict[str, str] = field(default_factory=dict)

    # ── Phase 2: processed / enriched data ───────────────────────────────
    # Written by MQManagerProcessorStep (after process_assets + convert_to_json)
    directorate_data: Dict = field(default_factory=dict)
    # Written by HierarchyEnrichmentStep (Org→Dept→BizOwner→App→QM tree)
    enriched_data:    Dict = field(default_factory=dict)

    # ── Phase 3: analysis results ─────────────────────────────────────────
    # Written by ChangeDetectionStep
    changes:           Optional[Dict] = None
    baseline_time_str: Optional[str]  = None
    # Written by GatewayAnalyticsStep
    gateway_analytics: Optional[Dict] = None

    # ── Output file paths (read by Publisher steps) ───────────────────────
    consolidated_report_file: Optional[Any] = None   # pathlib.Path
    ea_doc_file:              Optional[Any] = None   # pathlib.Path

    # ── Shared metadata ───────────────────────────────────────────────────
    # YYYYMMDD_HHMMSS string — used in all timestamped output filenames
    timestamp: str = ""

    # ── Infrastructure ────────────────────────────────────────────────────
    config:          Any       = None   # config.settings.Config
    logger:          Any       = None   # logging.Logger instance
    pipeline_errors: List[str] = field(default_factory=list)

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    def record_error(self, label: str, exc: Exception) -> None:
        """Log a non-fatal warning and record it for the end-of-run summary.

        Use this inside execute() for errors that should NOT abort the pipeline.
        For fatal errors, raise the exception directly.

        Args:
            label: Short description of the step that failed (e.g. "Topology diagram")
            exc:   The exception that was caught
        """
        msg = f"{label}: {exc}"
        self.pipeline_errors.append(msg)
        if self.logger:
            self.logger.warning(f"⚠ {msg}")


# ──────────────────────────────────────────────────────────────────────────────
# Abstract base class for all pipeline steps
# ──────────────────────────────────────────────────────────────────────────────

class PipelineComponent(ABC):
    """Base for every step in the pipeline.

    Class-level attributes are set by the @PluginRegistry.register() decorator
    and read by the generic orchestrator. Subclasses should override ``name``
    and optionally ``abort_on_failure`` and ``parallel_group``.

    Attributes:
        name:             Human-readable label used in log output.
        parallel_group:   Steps sharing the same non-empty group string are
                          submitted to a ThreadPoolExecutor together.
                          Leave as "" for sequential execution.
        abort_on_failure: If True, an unhandled exception inside execute()
                          terminates the entire pipeline. If False, the error
                          is recorded and execution continues with the next step.
    """

    name:             str  = ""
    parallel_group:   str  = ""      # "" → sequential; shared string → concurrent
    abort_on_failure: bool = False   # True only for steps whose output is mandatory

    @abstractmethod
    def execute(self, context: PipelineContext) -> None:
        """Run this pipeline step.

        Contract:
        - Read required inputs from ``context``.
        - Write outputs back to ``context``.
        - For non-fatal errors, call ``context.record_error(label, exc)``
          and return normally so the pipeline continues.
        - For fatal errors (missing mandatory data, etc.), raise so the
          orchestrator can handle the abort correctly.

        Args:
            context: Shared pipeline data bag
        """


# ──────────────────────────────────────────────────────────────────────────────
# Role sub-classes
# Semantic grouping only — no additional abstract methods.
# Allows isinstance(step, Generator) type checks in the orchestrator.
# ──────────────────────────────────────────────────────────────────────────────

class Processor(PipelineComponent):
    """Transforms raw or intermediate data into a more structured form."""


class Generator(PipelineComponent):
    """Produces output files: DOT diagrams, HTML reports, Excel, text docs…"""


class Analyzer(PipelineComponent):
    """Runs analysis and writes result dicts back to PipelineContext."""


class Publisher(PipelineComponent):
    """Pushes generated outputs to an external system (Confluence, etc.)."""


class Notifier(PipelineComponent):
    """Sends a notification about pipeline completion (email, Slack, etc.)."""
