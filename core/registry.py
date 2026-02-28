"""
Plugin registry for the MQ CMDB pipeline.

Components self-register with a single decorator applied to their class:

    from core.interfaces import Generator, PipelineContext
    from core.registry import PluginRegistry

    @PluginRegistry.register(order=6, parallel_group="diagrams")
    class HierarchicalGraphVizGenerator(Generator):
        name = "Hierarchical Topology Diagram"

        def execute(self, context: PipelineContext) -> None:
            ...

The orchestrator calls ``PluginRegistry.get_ordered_steps()`` to retrieve all
registered steps in execution order. It never imports any component class by
name — it only knows about the registry.

Adding a new pipeline step
--------------------------
1. Create a new .py file (or add a class to an existing one).
2. Apply @PluginRegistry.register(order=N) to your class.
3. Ensure the module is imported at startup (auto-discovery in main.py handles
   this for files in processors/, generators/, analytics/, and utils/).
4. That's it — orchestrator.py is never touched.

Execution order numbers
-----------------------
Use the same numbering as the original orchestrator steps:
    0     Output cleanup
    1     Data ingestion (load JSON, build host/alias maps)
    2     MQ Manager relationship processing
    3.5   Confluence input file sync
    4     Hierarchy enrichment
    5     Change detection
    6-8   Diagram generation (parallel_group="diagrams")
    9     Smart filtered views
    10    Gateway analytics
    10.5  Consolidated report
    11    Multi-format exports
    12    EA documentation
    12.5  Confluence publishing
    14    Email notification

Use float order values (e.g. 7.5) to insert new steps between existing ones
without renumbering the whole sequence.
"""

from __future__ import annotations

from itertools import groupby
from typing import Iterator, List, Tuple, Type

from core.interfaces import PipelineComponent


class PluginRegistry:
    """Central registry of all pipeline step classes.

    All interaction happens through class methods — there is no instance.
    The ``_steps`` list is populated by the ``@register`` decorator as each
    component module is imported.
    """

    _steps: List[Type[PipelineComponent]] = []

    # ──────────────────────────────────────────────────────────────────────
    # Registration
    # ──────────────────────────────────────────────────────────────────────

    @classmethod
    def register(cls, order: float, parallel_group: str = ""):
        """Decorator factory that registers a PipelineComponent subclass.

        Args:
            order:          Numeric execution position. Steps run in ascending
                            order. Use floats to insert between existing steps.
            parallel_group: Steps with the same non-empty group string are
                            submitted to a thread pool concurrently.
                            Steps with "" run sequentially.

        Returns:
            The unmodified class (decorator is transparent to callers).

        Example::

            @PluginRegistry.register(order=10.5)
            class ConsolidatedReportStep(Generator):
                name = "Consolidated Report"
                def execute(self, context): ...
        """
        def decorator(klass: Type[PipelineComponent]) -> Type[PipelineComponent]:
            # Attach order and group as class attributes so the orchestrator
            # can read them without needing special knowledge of each class.
            klass._order          = order          # type: ignore[attr-defined]
            klass.parallel_group  = parallel_group
            cls._steps.append(klass)
            return klass
        return decorator

    # ──────────────────────────────────────────────────────────────────────
    # Querying
    # ──────────────────────────────────────────────────────────────────────

    @classmethod
    def get_ordered_steps(cls) -> List[Type[PipelineComponent]]:
        """Return all registered step classes sorted by their order number.

        Steps disabled via Config.PIPELINE_STEPS are still returned here;
        the orchestrator applies the enable/disable filter at run time.
        """
        return sorted(cls._steps, key=lambda k: getattr(k, '_order', 99))

    @classmethod
    def iter_groups(
        cls,
        steps: List[Type[PipelineComponent]] | None = None,
    ) -> Iterator[Tuple[str, List[Type[PipelineComponent]]]]:
        """Yield (group_key, [StepClass, ...]) pairs in execution order.

        Consecutive steps that share the same non-empty ``parallel_group``
        string are yielded together in a single batch. All other steps are
        yielded one at a time with an empty group key.

        This drives the orchestrator's parallel-vs-sequential branching:

            for group_key, batch in PluginRegistry.iter_groups(steps):
                if group_key:
                    # submit batch concurrently
                else:
                    # run the single step sequentially

        Args:
            steps: Pre-filtered step list (optional). Defaults to all
                   registered steps in execution order.
        """
        if steps is None:
            steps = cls.get_ordered_steps()
        for group_key, batch in groupby(steps, key=lambda s: s.parallel_group):
            yield group_key, list(batch)

    # ──────────────────────────────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────────────────────────────

    @classmethod
    def clear(cls) -> None:
        """Reset the registry. Use in unit tests to avoid cross-test pollution."""
        cls._steps = []

    @classmethod
    def summary(cls) -> str:
        """Return a human-readable list of registered steps for diagnostics."""
        lines = ["Registered pipeline steps:"]
        for klass in cls.get_ordered_steps():
            order = getattr(klass, '_order', '?')
            group = klass.parallel_group or "sequential"
            abort = " [abort-on-fail]" if klass.abort_on_failure else ""
            lines.append(
                f"  [{order:>5}] {klass.name or klass.__name__:<45} ({group}){abort}"
            )
        return "\n".join(lines)
