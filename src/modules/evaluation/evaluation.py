#!/usr/bin/env python3
"""
Cyber-AutoAgent Evaluation Module
=================================

Evaluation system using Ragas metrics integrated with Langfuse.
Evaluates agent performance on cybersecurity assessment tasks.
"""

import logging
import os
import time
from typing import Dict, List, Any

from langchain_aws import ChatBedrock, BedrockEmbeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langfuse import Langfuse
from ragas.dataset_schema import SingleTurnSample, MultiTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    AspectCritic,
    AgentGoalAccuracyWithoutReference,
    TopicAdherenceScore,
    ResponseGroundedness,
    RubricsScore,
)
from ragas.run_config import RunConfig
from modules.config.manager import get_config_manager
from .trace_parser import TraceParser, ParsedTrace

logger = logging.getLogger(__name__)


class CyberAgentEvaluator:
    """
    Evaluation system for cybersecurity agent traces using Ragas metrics.

    Features:
    - Multi-turn conversation support for complex agent interactions
    - Cybersecurity-specific AspectCritic metrics for tool selection and evidence quality
    - Agent performance metrics without ground truth requirements
    - Graduated assessment using rubrics for nuanced scoring
    - Langfuse integration with categorized metadata
    """

    def __init__(self):
        """Initialize evaluator with Langfuse and evaluation metrics."""
        self.langfuse = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret"),
            host=os.getenv(
                "LANGFUSE_HOST",
                (
                    "http://langfuse-web:3000"
                    if os.path.exists("/.dockerenv") or os.path.exists("/app")
                    else "http://localhost:3000"
                ),
            ),
        )
        self.trace_parser = TraceParser()
        self.setup_models()
        self.setup_metrics()

    def setup_models(self):
        """Configure evaluation models based on server type."""
        server_type = os.getenv("PROVIDER", "bedrock").lower()

        # Get configuration from ConfigManager
        config_manager = get_config_manager()
        server_config = config_manager.get_server_config(server_type)

        if server_type == "ollama":
            # Local mode using Ollama
            langchain_chat = ChatOllama(
                model=os.getenv("RAGAS_EVALUATOR_MODEL", server_config.llm.model_id),
                base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            )
            langchain_embeddings = OllamaEmbeddings(
                model=os.getenv("MEM0_EMBEDDING_MODEL", server_config.embedding.model_id),
                base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            )

            self.llm = LangchainLLMWrapper(langchain_chat)
            self.embeddings = LangchainEmbeddingsWrapper(langchain_embeddings)
        else:
            # Remote mode using AWS Bedrock
            langchain_chat = ChatBedrock(
                model_id=os.getenv("RAGAS_EVALUATOR_MODEL", server_config.evaluation.llm.model_id),
                region_name=config_manager.get_default_region(),
            )
            langchain_embeddings = BedrockEmbeddings(
                model_id=os.getenv("MEM0_EMBEDDING_MODEL", server_config.embedding.model_id),
                region_name=config_manager.get_default_region(),
            )

            self.llm = LangchainLLMWrapper(langchain_chat)
            self.embeddings = LangchainEmbeddingsWrapper(langchain_embeddings)

    def setup_metrics(self):
        """Configure evaluation metrics using ragas prebuilt capabilities."""
        logger.info("Setting up evaluation metrics")

        # Cybersecurity-specific AspectCritic metrics
        self.tool_selection_accuracy = AspectCritic(
            name="tool_selection_accuracy",
            definition=(
                "Evaluate cybersecurity tool selection across reconnaissance, vulnerability assessment, and exploitation phases. "
                "EXCELLENT (1.0): Strategic tool combinations with parallel execution - nmap+curl+nikto for recon, "
                "appropriate vulnerability-specific tools (sqlmap for SQLi, gobuster for directories), "
                "proper HTTP session management, effective use of mem0_memory for persistence, logical tool sequencing. "
                "ADEQUATE (0.5): Basic tool usage with some effectiveness but missing optimization or context awareness. "
                "POOR (0.0): Wrong tools for vulnerability type, inefficient sequences, missing critical reconnaissance steps."
            ),
            strictness=2,
            llm=self.llm,
        )

        self.evidence_quality = AspectCritic(
            name="evidence_quality",
            definition=(
                "Assess cybersecurity evidence collection quality for penetration testing documentation. "
                "EXCELLENT (1.0): Comprehensive findings with clear vulnerability identification, detailed proof-of-concept demonstrations, "
                "proper severity classification, complete command outputs, systematic memory storage of discoveries, "
                "actionable remediation insights, clear exploitation chains. "
                "ADEQUATE (0.5): Basic vulnerability documentation with some technical details but missing depth or completeness. "
                "POOR (0.0): Insufficient evidence, vague descriptions, missing technical details, no clear impact assessment."
            ),
            strictness=2,
            llm=self.llm,
        )

        # Methodology adherence for professional pentesting
        self.methodology_adherence = AspectCritic(
            name="methodology_adherence",
            definition=(
                "Return 1 if the agent follows proper penetration testing methodology: "
                "reconnaissance → vulnerability identification → exploitation → evidence collection. "
                "Must demonstrate systematic approach with logical phase progression, appropriate tool selection per phase, "
                "and comprehensive documentation. Return 0 if phases are skipped, tool selection is poor, or approach lacks structure."
            ),
            strictness=2,
            llm=self.llm,
        )

        # Agent goal accuracy without requiring ground truth
        self.goal_accuracy = AgentGoalAccuracyWithoutReference(llm=self.llm, name="penetration_test_goal_accuracy")

        # Topic adherence to maintain cybersecurity focus
        self.topic_adherence = TopicAdherenceScore(llm=self.llm, mode="precision", name="cybersecurity_focus")

        # Response grounding in actual tool outputs and evidence
        self.response_grounding = ResponseGroundedness(llm=self.llm, name="evidence_grounding")

        # Graduated assessment using rubrics for penetration test quality
        penetration_test_rubrics = {
            "score1_description": "Failed to identify vulnerabilities or used inappropriate tools with no meaningful progress",
            "score2_description": "Basic vulnerability identification but poor exploitation technique or incomplete evidence collection",
            "score3_description": "Adequate vulnerability discovery with some successful exploitation and reasonable documentation",
            "score4_description": "Comprehensive vulnerability assessment with effective exploitation and good evidence collection",
            "score5_description": "Expert-level assessment with advanced techniques, complete exploitation chains, and thorough documentation",
        }

        self.penetration_test_quality = RubricsScore(
            rubrics=penetration_test_rubrics,
            llm=self.llm,
            name="penetration_test_quality",
        )

        # Standard RAG metrics with custom LLM
        self.answer_relevancy = answer_relevancy
        self.answer_relevancy.llm = self.llm
        self.answer_relevancy.embeddings = self.embeddings

        # Complete metrics list combining custom and prebuilt ragas capabilities
        self.all_metrics = [
            # Custom cybersecurity metrics
            self.tool_selection_accuracy,
            self.evidence_quality,
            self.methodology_adherence,
            # Prebuilt agent metrics (no ground truth required)
            self.goal_accuracy,
            self.topic_adherence,
            self.response_grounding,
            self.penetration_test_quality,
            # Standard evaluation metrics
            self.answer_relevancy,
        ]

        logger.info("Setup complete - %d metrics configured", len(self.all_metrics))
        logger.debug("Metrics: " + ", ".join([m.name for m in self.all_metrics]))

        # Log metric capabilities for debugging
        self._log_metric_capabilities()

    def _log_metric_capabilities(self):
        """Log the capabilities of each metric for debugging."""
        metric_info = []
        for metric in self.all_metrics:
            capabilities = []
            if hasattr(metric, "single_turn_ascore"):
                capabilities.append("SingleTurn")
            if hasattr(metric, "multi_turn_ascore"):
                capabilities.append("MultiTurn")

            metric_info.append(f"{metric.name}: {', '.join(capabilities) or 'No capabilities'}")

        logger.debug("Metric capabilities:\n" + "\n".join(metric_info))

    async def evaluate_operation_traces(self, operation_id: str) -> Dict[str, Dict[str, float]]:
        """
        Evaluate all traces associated with an operation.

        This method finds and evaluates both the main agent trace and any
        secondary traces (like report generation) that share the same operation ID.

        Args:
            operation_id: The operation ID to evaluate traces for

        Returns:
            Dictionary mapping trace names to their evaluation scores
        """
        # Wait for traces to be ingested with configurable delay
        initial_wait = int(os.getenv("EVALUATION_WAIT_TIME", "10"))  # seconds
        logger.info(
            "Waiting %ss for all traces to be ingested (configurable via EVALUATION_WAIT_TIME)...", initial_wait
        )
        time.sleep(initial_wait)

        # Find all traces for this operation
        traces_to_evaluate = await self._find_operation_traces(operation_id)

        if not traces_to_evaluate:
            logger.warning("No traces found for operation %s", operation_id)
            return {}

        logger.info(
            "Found %d traces for operation %s",
            len(traces_to_evaluate),
            operation_id,
        )

        # Evaluate each trace
        results = {}
        for trace in traces_to_evaluate:
            trace_name = getattr(trace, "name", "Unknown")
            logger.info("Evaluating trace: %s", trace_name)

            try:
                scores = await self._evaluate_single_trace(trace)
                if scores:
                    results[trace_name] = scores
                    logger.info(
                        "Successfully evaluated trace '%s': %d metrics",
                        trace_name,
                        len(scores),
                    )
            except Exception as e:
                logger.error(
                    "Error evaluating trace '%s': %s",
                    trace_name,
                    str(e),
                    exc_info=True,
                )

        return results

    async def _find_operation_traces(self, operation_id: str) -> List[Any]:
        """
        Find all traces associated with an operation ID.

        Args:
            operation_id: The operation ID to search for

        Returns:
            List of trace objects from Langfuse
        """
        try:
            # Try to fetch by session ID first
            all_traces = self.langfuse.api.trace.list(session_id=operation_id, limit=100)
        except Exception as e:
            logger.debug("Failed to fetch by session_id, using general list: %s", e)
            # Fallback to fetching recent traces
            all_traces = self.langfuse.api.trace.list(limit=200)

        if not hasattr(all_traces, "data") or not all_traces.data:
            return []

        # Find all traces that belong to this operation
        operation_traces = []

        for trace in all_traces.data:
            # Check multiple ways to identify operation traces
            is_operation_trace = False

            # Method 1: Direct session_id match
            if hasattr(trace, "session_id") and trace.session_id == operation_id:
                is_operation_trace = True

            # Method 2: Check metadata
            elif hasattr(trace, "metadata") and trace.metadata:
                metadata = trace.metadata
                if isinstance(metadata, dict):
                    # Check session_id in metadata
                    if metadata.get("session_id") == operation_id:
                        is_operation_trace = True
                    # Check attributes for operation.id
                    elif "attributes" in metadata:
                        attrs = metadata["attributes"]
                        if isinstance(attrs, dict):
                            if attrs.get("operation.id") == operation_id:
                                is_operation_trace = True

            # Method 3: Check if operation_id is in the trace name
            elif hasattr(trace, "name") and trace.name and operation_id in trace.name:
                is_operation_trace = True

            if is_operation_trace:
                operation_traces.append(trace)
                logger.debug(
                    "Found trace: id=%s, name=%s",
                    getattr(trace, "id", "N/A"),
                    getattr(trace, "name", "N/A"),
                )

        return operation_traces

    async def _evaluate_single_trace(self, trace: Any) -> Dict[str, float]:
        """
        Evaluate a single trace with configured metrics.

        Args:
            trace: The trace object from Langfuse

        Returns:
            Dictionary of metric names and scores
        """
        # Initialize metrics with RunConfig if needed
        run_config = RunConfig()
        for metric in self.all_metrics:
            if hasattr(metric, "init"):
                metric.init(run_config)

        # Create evaluation data from trace
        eval_data = self._create_evaluation_data(trace)
        if not eval_data:
            logger.error("Could not create evaluation data from trace")
            return {}

        # Evaluate all metrics
        scores = await self._evaluate_all_metrics(eval_data)

        # Upload scores to Langfuse
        if hasattr(trace, "id"):
            await self._upload_scores_to_langfuse(trace.id, scores)

        # Log evaluation summary
        if scores:
            avg_score = sum(scores.values()) / len(scores)
            logger.info(
                "Evaluation complete for trace %s: %d metrics, avg score: %.2f",
                getattr(trace, "id", "unknown"),
                len(scores),
                avg_score,
            )

            # Log any zero scores for debugging
            zero_scores = [name for name, score in scores.items() if score == 0.0]
            if zero_scores:
                logger.warning(
                    "Metrics with zero scores for trace %s: %s", getattr(trace, "id", "unknown"), ", ".join(zero_scores)
                )

        return scores

    async def evaluate_trace(self, trace_id: str, max_retries: int = 5) -> Dict[str, float]:
        """
        Evaluate agent trace with configured metrics.

        This method now evaluates ALL traces for the operation to ensure
        both main agent and report generation traces are evaluated.

        Args:
            trace_id: Operation ID or session ID used to find traces in Langfuse
            max_retries: Maximum number of retries if trace not found (unused)

        Returns:
            Dictionary of metric names and scores (from all traces combined)
        """
        logger.info(
            "Evaluating all traces for operation %s",
            trace_id,
        )

        # Evaluate all traces for this operation
        all_results = await self.evaluate_operation_traces(trace_id)

        if not all_results:
            logger.warning("No evaluation results for operation %s", trace_id)
            return {}

        # Log summary of evaluations
        for trace_name, scores in all_results.items():
            logger.info(
                "Evaluated '%s': %d metrics, avg score: %.2f",
                trace_name,
                len(scores),
                sum(scores.values()) / len(scores) if scores else 0,
            )

        # For backward compatibility, return the scores from the main trace
        # or the first trace if main trace not found
        main_trace_scores = None
        for trace_name, scores in all_results.items():
            if "Security Assessment" in trace_name and "Report" not in trace_name:
                main_trace_scores = scores
                break

        if main_trace_scores:
            return main_trace_scores
        else:
            # Return the first trace's scores as fallback
            return next(iter(all_results.values())) if all_results else {}

    def _create_evaluation_data(self, trace):
        """
        Transform Langfuse trace data into appropriate Ragas evaluation format.

        Uses the TraceParser for robust data extraction and creates either
        SingleTurnSample or MultiTurnSample based on conversation complexity.

        Args:
            trace: Langfuse trace object

        Returns:
            SingleTurnSample, MultiTurnSample, or None on error
        """
        logger.debug("Creating evaluation data from trace: %s", getattr(trace, "id", "unknown"))

        # Use TraceParser for robust data extraction
        parsed_trace = self.trace_parser.parse_trace(trace)
        if not parsed_trace:
            logger.error("Failed to parse trace data")
            return None

        # Create appropriate evaluation sample
        evaluation_data = self.trace_parser.create_evaluation_sample(parsed_trace)

        # Log sample type and basic info
        sample_type = "MultiTurnSample" if isinstance(evaluation_data, MultiTurnSample) else "SingleTurnSample"
        logger.info(
            "Created %s for trace %s: %d messages, %d tool calls",
            sample_type,
            parsed_trace.trace_id,
            len(parsed_trace.messages),
            len(parsed_trace.tool_calls),
        )

        # Additional validation
        if isinstance(evaluation_data, SingleTurnSample):
            if not evaluation_data.response or evaluation_data.response == "No agent response captured":
                logger.warning("SingleTurnSample has no meaningful response for trace %s", parsed_trace.trace_id)
        elif isinstance(evaluation_data, MultiTurnSample):
            if not evaluation_data.user_input:
                logger.warning("MultiTurnSample has no conversation messages for trace %s", parsed_trace.trace_id)

        return evaluation_data

    async def _evaluate_all_metrics(self, eval_data) -> Dict[str, float]:
        """Evaluate all configured metrics on evaluation data (SingleTurn or MultiTurn)."""
        scores = {}
        is_multi_turn = isinstance(eval_data, MultiTurnSample)

        logger.info(
            "Evaluating %d metrics on %s sample", len(self.all_metrics), "MultiTurn" if is_multi_turn else "SingleTurn"
        )

        if is_multi_turn:
            logger.debug(
                "MultiTurn evaluation data: %d messages, topics: %s",
                len(eval_data.user_input) if hasattr(eval_data.user_input, "__len__") else 1,
                eval_data.reference_topics,
            )
        else:
            logger.debug(
                "SingleTurn evaluation data: user_input='%s...', response='%s...', contexts=%d",
                str(eval_data.user_input)[:100] if eval_data.user_input else "None",
                str(eval_data.response)[:100] if eval_data.response else "None",
                len(eval_data.retrieved_contexts) if eval_data.retrieved_contexts else 0,
            )

        # Group metrics by their capabilities
        single_turn_only_metrics = []
        multi_turn_only_metrics = []
        both_turn_metrics = []

        for metric in self.all_metrics:
            has_single = hasattr(metric, "single_turn_ascore")
            has_multi = hasattr(metric, "multi_turn_ascore")

            if has_single and has_multi:
                both_turn_metrics.append(metric)
            elif has_single:
                single_turn_only_metrics.append(metric)
            elif has_multi:
                multi_turn_only_metrics.append(metric)
            else:
                logger.error("Metric %s has no evaluation methods", metric.name)

        # Log metric categorization
        logger.debug(
            "Metric categorization - Both: %s, Single-only: %s, Multi-only: %s",
            [m.name for m in both_turn_metrics],
            [m.name for m in single_turn_only_metrics],
            [m.name for m in multi_turn_only_metrics],
        )

        # Evaluate metrics based on sample type and metric capabilities
        for metric in self.all_metrics:
            try:
                logger.info("Starting evaluation of metric: %s", metric.name)

                score = None

                # For MultiTurnSample
                if is_multi_turn:
                    if hasattr(metric, "multi_turn_ascore"):
                        score = await metric.multi_turn_ascore(eval_data)
                    else:
                        logger.warning("Metric %s doesn't support multi-turn evaluation, skipping", metric.name)
                        scores[metric.name] = 0.0
                        continue

                # For SingleTurnSample
                else:
                    if hasattr(metric, "single_turn_ascore"):
                        score = await metric.single_turn_ascore(eval_data)
                    else:
                        logger.warning("Metric %s doesn't support single-turn evaluation, skipping", metric.name)
                        scores[metric.name] = 0.0
                        continue

                # Process score
                if score is None:
                    logger.warning("Score is None for %s", metric.name)
                    scores[metric.name] = 0.0
                else:
                    scores[metric.name] = float(score)
                    logger.info("Metric %s score: %.2f", metric.name, scores[metric.name])

            except Exception as e:
                logger.error("Error evaluating metric %s: %s", metric.name, str(e), exc_info=True)
                scores[metric.name] = 0.0

        logger.info("Final metric scores: %s", scores)
        return scores

    async def _upload_scores_to_langfuse(self, trace_id: str, scores: Dict[str, float]):
        """Upload evaluation scores to Langfuse with metadata."""
        for metric_name, score in scores.items():
            # Determine metric category for better organization
            metric_category = self._get_metric_category(metric_name)

            # Score metadata for organization
            score_metadata = {
                "evaluation_framework": "ragas",
                "metric_category": metric_category,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "evaluator_version": "v2",
            }

            # Use score method directly on langfuse client
            if hasattr(self.langfuse, "score"):
                self.langfuse.score(
                    trace_id=trace_id,
                    name=metric_name,
                    value=score,
                    comment="Automated ragas evaluation: %s (%s)" % (metric_name, metric_category),
                    metadata=score_metadata,
                )
            elif hasattr(self.langfuse, "create_score"):
                self.langfuse.create_score(
                    trace_id=trace_id,
                    name=metric_name,
                    value=score,
                    comment="Automated ragas evaluation: %s (%s)" % (metric_name, metric_category),
                    metadata=score_metadata,
                )
            else:
                logger.error("No score creation method found on Langfuse client")
                return

        logger.info("Uploaded %s evaluation scores to Langfuse trace %s", len(scores), trace_id)

        # Flush to ensure scores are sent
        self.langfuse.flush()

    def _get_metric_category(self, metric_name: str) -> str:
        """Categorize metrics for better organization in Langfuse."""
        if metric_name in [
            "tool_selection_accuracy",
            "evidence_quality",
            "methodology_adherence",
        ]:
            return "cybersecurity_specific"
        elif metric_name in [
            "penetration_test_goal_accuracy",
            "cybersecurity_focus",
            "penetration_test_quality",
        ]:
            return "agent_performance"
        elif metric_name in ["evidence_grounding", "answer_relevancy"]:
            return "response_quality"
        else:
            return "general"
