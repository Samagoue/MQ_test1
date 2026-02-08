"""Parallel execution framework for diagram generation.

Uses concurrent.futures.ThreadPoolExecutor for I/O-bound GraphViz
subprocess calls. Each task runs in its own thread with fault isolation
so one failure does not crash other tasks.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logging_config import get_logger

logger = get_logger("parallel")

DEFAULT_WORKERS = min(4, os.cpu_count() or 2)


class DiagramTask:
    """Encapsulates a single diagram generation task."""

    __slots__ = ('name', 'fn', 'args', 'kwargs')

    def __init__(self, name, fn, *args, **kwargs):
        self.name = name
        self.fn = fn
        self.args = args
        self.kwargs = kwargs


class ParallelResult:
    """Result of parallel execution."""

    def __init__(self):
        self.succeeded = []
        self.failed = []

    @property
    def success_count(self):
        return len(self.succeeded)

    @property
    def failure_count(self):
        return len(self.failed)

    @property
    def total(self):
        return self.success_count + self.failure_count


def run_parallel(tasks, max_workers=None):
    """
    Execute tasks in parallel with error isolation.

    Each failed task is caught and recorded; it does NOT crash other tasks.
    Falls back to sequential execution for single tasks or single worker.

    Args:
        tasks: List of DiagramTask instances.
        max_workers: Maximum number of parallel workers. None uses the default.

    Returns:
        ParallelResult with succeeded/failed task names.
    """
    if max_workers is None:
        max_workers = DEFAULT_WORKERS

    if not tasks:
        return ParallelResult()

    # For single task or single worker, run sequentially
    if len(tasks) <= 1 or max_workers <= 1:
        return _run_sequential(tasks)

    result = ParallelResult()
    total = len(tasks)

    logger.info(f"Starting parallel execution: {total} tasks, {max_workers} workers")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(task.fn, *task.args, **task.kwargs): task
            for task in tasks
        }

        for idx, future in enumerate(as_completed(future_to_task), 1):
            task = future_to_task[future]
            try:
                future.result()
                result.succeeded.append(task.name)
                logger.debug(f"  [{idx}/{total}] {task.name} -- done")
            except Exception as e:
                result.failed.append({'name': task.name, 'error': str(e)})
                logger.warning(f"  [{idx}/{total}] {task.name} -- FAILED: {e}")

    logger.info(
        f"Parallel execution complete: {result.success_count} succeeded, "
        f"{result.failure_count} failed"
    )
    return result


def _run_sequential(tasks):
    """Run tasks sequentially (fallback for single task/worker)."""
    result = ParallelResult()
    total = len(tasks)

    for idx, task in enumerate(tasks, 1):
        try:
            task.fn(*task.args, **task.kwargs)
            result.succeeded.append(task.name)
            logger.debug(f"  [{idx}/{total}] {task.name} -- done")
        except Exception as e:
            result.failed.append({'name': task.name, 'error': str(e)})
            logger.warning(f"  [{idx}/{total}] {task.name} -- FAILED: {e}")

    return result
