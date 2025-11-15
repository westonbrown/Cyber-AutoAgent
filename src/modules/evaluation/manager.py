#!/usr/bin/env python3
"""
Evaluation Manager for Cyber-AutoAgent
======================================

Manages evaluation of multiple traces within an operation, ensuring both main agent
and report generation traces are properly evaluated.

This module provides:
- Tracking of multiple trace IDs per operation
- Coordinated evaluation of all traces
- Proper trace type identification for metrics selection
"""

import asyncio
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .evaluation import CyberAgentEvaluator
from modules.config.system.logger import get_logger

logger = get_logger("Evaluation.Manager")


class TraceType(Enum):
    """Types of traces that can be evaluated."""

    MAIN_AGENT = "main_agent"
    REPORT_GENERATION = "report_generation"
    SWARM_AGENT = "swarm_agent"


@dataclass
class TraceInfo:
    """Information about a trace to be evaluated."""

    trace_id: str
    trace_type: TraceType
    session_id: str
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    evaluated: bool = False
    evaluation_scores: Optional[Dict[str, float]] = None


class EvaluationManager:
    """
    Manages evaluation of multiple traces within an operation.

    This class ensures that all traces associated with an operation are properly
    evaluated, including the main agent trace and any secondary traces like
    report generation.
    """

    def __init__(self, operation_id: str):
        """
        Initialize the evaluation manager.

        Args:
            operation_id: The operation ID to manage evaluations for
        """
        self.operation_id = operation_id
        self.traces: Dict[str, TraceInfo] = {}
        self.evaluator: Optional[CyberAgentEvaluator] = None
        self._lock = threading.Lock()
        self._evaluation_thread: Optional[threading.Thread] = None
        self._evaluation_complete = threading.Event()

    def register_trace(
        self,
        trace_id: str,
        trace_type: TraceType,
        session_id: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a trace for evaluation.

        Args:
            trace_id: The unique trace ID
            trace_type: Type of trace (main_agent, report_generation, etc.)
            session_id: Session ID associated with the trace
            name: Human-readable name for the trace
            metadata: Optional metadata about the trace
        """
        with self._lock:
            self.traces[trace_id] = TraceInfo(
                trace_id=trace_id,
                trace_type=trace_type,
                session_id=session_id,
                name=name,
                metadata=metadata or {},
            )
            logger.info(
                "Registered trace for evaluation: %s (%s) - %s",
                trace_id,
                trace_type.value,
                name,
            )

    def get_trace_ids_by_type(self, trace_type: TraceType) -> List[str]:
        """
        Get all trace IDs of a specific type.

        Args:
            trace_type: The type of traces to retrieve

        Returns:
            List of trace IDs matching the specified type
        """
        with self._lock:
            return [
                trace_id
                for trace_id, info in self.traces.items()
                if info.trace_type == trace_type
            ]

    def get_unevaluated_traces(self) -> List[TraceInfo]:
        """
        Get all traces that haven't been evaluated yet.

        Returns:
            List of TraceInfo objects for unevaluated traces
        """
        with self._lock:
            return [info for info in self.traces.values() if not info.evaluated]

    async def evaluate_all_traces(self) -> Dict[str, Dict[str, float]]:
        """
        Evaluate all registered traces.

        Returns:
            Dictionary mapping trace IDs to their evaluation scores
        """
        # Initialize evaluator if not already done
        if not self.evaluator:
            self.evaluator = CyberAgentEvaluator()

        results = {}
        unevaluated = self.get_unevaluated_traces()

        if not unevaluated:
            logger.info(
                "No unevaluated traces found for operation %s", self.operation_id
            )
            return results

        logger.info(
            "Starting evaluation of %d traces for operation %s",
            len(unevaluated),
            self.operation_id,
        )

        # Evaluate each trace
        for trace_info in unevaluated:
            try:
                logger.info(
                    "Evaluating %s trace: %s",
                    trace_info.trace_type.value,
                    trace_info.name,
                )

                # Use session_id for evaluation (Langfuse uses this for lookup)
                scores = await self.evaluator.evaluate_trace(
                    trace_id=trace_info.session_id,
                    _max_retries=5,
                )

                if scores:
                    # Normalize to floats for storage in manager (rubric metrics may be (value, metadata))
                    numeric_scores = {}
                    try:
                        for k, v in (scores or {}).items():
                            if isinstance(v, tuple) and len(v) >= 1:
                                v = v[0]
                            if isinstance(v, (int, float)):
                                numeric_scores[k] = float(v)
                    except Exception:
                        numeric_scores = {
                            k: (float(v[0]) if isinstance(v, tuple) else float(v))
                            for k, v in scores.items()
                            if isinstance(v, (int, float))
                            or (isinstance(v, tuple) and len(v) >= 1)
                        }

                    with self._lock:
                        self.traces[trace_info.trace_id].evaluated = True
                        self.traces[
                            trace_info.trace_id
                        ].evaluation_scores = numeric_scores

                    results[trace_info.trace_id] = numeric_scores
                    logger.info(
                        "Successfully evaluated trace %s: %d metrics",
                        trace_info.trace_id,
                        len(numeric_scores),
                    )
                else:
                    logger.warning(
                        "No scores returned for trace %s",
                        trace_info.trace_id,
                    )

            except Exception as e:
                logger.error(
                    "Error evaluating trace %s: %s",
                    trace_info.trace_id,
                    str(e),
                    exc_info=True,
                )

        logger.info(
            "Completed evaluation of operation %s: %d/%d traces evaluated successfully",
            self.operation_id,
            len(results),
            len(unevaluated),
        )

        return results

    def trigger_async_evaluation(self) -> None:
        """
        Trigger evaluation in a background thread.

        This method starts the evaluation process asynchronously and returns
        immediately.
        """
        if self._evaluation_thread and self._evaluation_thread.is_alive():
            logger.warning(
                "Evaluation already in progress for operation %s", self.operation_id
            )
            return

        def run_evaluation():
            """Run the evaluation in a separate thread."""
            try:
                logger.info(
                    "Starting async evaluation for operation %s", self.operation_id
                )
                asyncio.run(self.evaluate_all_traces())
                self._evaluation_complete.set()
            except Exception as e:
                logger.error(
                    "Error in async evaluation for operation %s: %s",
                    self.operation_id,
                    str(e),
                    exc_info=True,
                )
                self._evaluation_complete.set()

        self._evaluation_thread = threading.Thread(
            target=run_evaluation,
            name=f"evaluation-{self.operation_id}",
        )
        self._evaluation_thread.daemon = True
        self._evaluation_thread.start()

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for evaluation to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if evaluation completed, False if timeout reached
        """
        if not self._evaluation_thread:
            return True

        return self._evaluation_complete.wait(timeout=timeout)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the evaluation status.

        Returns:
            Dictionary containing evaluation summary information
        """
        with self._lock:
            total_traces = len(self.traces)
            evaluated_traces = sum(1 for t in self.traces.values() if t.evaluated)

            # Group by trace type
            by_type = {}
            for trace_info in self.traces.values():
                trace_type = trace_info.trace_type.value
                if trace_type not in by_type:
                    by_type[trace_type] = {"total": 0, "evaluated": 0}
                by_type[trace_type]["total"] += 1
                if trace_info.evaluated:
                    by_type[trace_type]["evaluated"] += 1

            return {
                "operation_id": self.operation_id,
                "total_traces": total_traces,
                "evaluated_traces": evaluated_traces,
                "evaluation_complete": evaluated_traces == total_traces,
                "by_type": by_type,
                "traces": [
                    {
                        "trace_id": info.trace_id,
                        "type": info.trace_type.value,
                        "name": info.name,
                        "evaluated": info.evaluated,
                        "score_count": len(info.evaluation_scores)
                        if info.evaluation_scores
                        else 0,
                    }
                    for info in self.traces.values()
                ],
            }
