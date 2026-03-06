"""
Open-architecture interfaces for the MQ CMDB pipeline.

Defines the two primitives that make the pipeline extensible:

    PipelineContext — mutable bag of state shared between all steps
    PipelineStep    — ABC that every pipeline step must implement

To add a new step:
    1. Create a module in steps/ that subclasses PipelineStep
    2. Add an instance of it to PIPELINE_STEPS in steps/__init__.py
    No changes to orchestrator.py are required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PipelineContext:
    """All mutable state shared between pipeline steps.

    Steps read what they need and write their outputs back here so that
    downstream steps can consume them without tight coupling.
    """

    # ── Required at construction ──────────────────────────────────────────
    config: Any                     # config.settings.Config

    # ── Set by orchestrator before the run ───────────────────────────────
    timestamp:     str  = ""        # YYYYmmdd_HHMMSS
    workers:       Optional[int] = None
    dry_run:       bool = False
    skip_export:   bool = False
    diagrams_only: bool = False

    # ── Populated by processing steps ────────────────────────────────────
    raw_data:            List[Dict]     = field(default_factory=list)
    directorate_data:    Dict           = field(default_factory=dict)
    enriched_data:       Dict           = field(default_factory=dict)
    changes:             Optional[Dict] = None
    baseline_time_str:   Optional[str]  = None
    gateway_analytics:   Optional[Dict] = None
    augmentation_records: List[Dict]   = field(default_factory=list)
    consolidated_report_file: Optional[Path] = None
    summary_stats:       Dict           = field(default_factory=dict)
    pdf_generated:       bool           = False

    # ── Error accumulator (non-fatal) ────────────────────────────────────
    errors: List[str] = field(default_factory=list)


class PipelineStep(ABC):
    """Base class for every pipeline step.

    Subclasses must implement ``name``, ``step_number``, and ``run()``.
    Override ``should_run()`` to add conditional execution logic.

    Example::

        class MyNewStep(PipelineStep):
            name        = "My New Step"
            step_number = "15"

            def should_run(self, ctx: PipelineContext) -> bool:
                return ctx.config.SOME_FLAG

            def run(self, ctx: PipelineContext) -> None:
                from my_module import do_something
                ctx.some_output = do_something(ctx.enriched_data)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable display name used in pipeline logging."""

    @property
    @abstractmethod
    def step_number(self) -> str:
        """Step label shown in pipeline output, e.g. '1', '1.5', '12.5'."""

    def should_run(self, ctx: PipelineContext) -> bool:
        """Return False to skip this step.  Default: always run."""
        return True

    @abstractmethod
    def run(self, ctx: PipelineContext) -> None:
        """Execute the step.  Read from ctx, write results back to ctx."""
