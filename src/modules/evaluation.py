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
from typing import Dict

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
from .config import get_config_manager

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
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
        )
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
                model=os.getenv(
                    "MEM0_EMBEDDING_MODEL", server_config.embedding.model_id
                ),
                base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            )

            self.llm = LangchainLLMWrapper(langchain_chat)
            self.embeddings = LangchainEmbeddingsWrapper(langchain_embeddings)
        else:
            # Remote mode using AWS Bedrock
            langchain_chat = ChatBedrock(
                model_id=os.getenv(
                    "RAGAS_EVALUATOR_MODEL", server_config.evaluation.llm.model_id
                ),
                region_name=config_manager.get_default_region(),
            )
            langchain_embeddings = BedrockEmbeddings(
                model_id=os.getenv(
                    "MEM0_EMBEDDING_MODEL", server_config.embedding.model_id
                ),
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
        self.goal_accuracy = AgentGoalAccuracyWithoutReference(
            llm=self.llm, name="penetration_test_goal_accuracy"
        )

        # Topic adherence to maintain cybersecurity focus
        self.topic_adherence = TopicAdherenceScore(
            llm=self.llm, mode="precision", name="cybersecurity_focus"
        )

        # Response grounding in actual tool outputs and evidence
        self.response_grounding = ResponseGroundedness(
            llm=self.llm, name="evidence_grounding"
        )

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

    async def evaluate_trace(
        self, trace_id: str, max_retries: int = 3
    ) -> Dict[str, float]:
        """
        Evaluate agent trace with configured metrics.

        Args:
            trace_id: Langfuse trace identifier
            max_retries: Maximum number of retries if trace not found

        Returns:
            Dictionary of metric names and scores
        """
        # Initialize metrics with RunConfig if needed
        run_config = RunConfig()
        for metric in self.all_metrics:
            if hasattr(metric, "init"):
                logger.debug("Initializing metric %s with RunConfig", metric.name)
                metric.init(run_config)

        for attempt in range(max_retries):
            # Fetch trace from Langfuse
            all_traces = self.langfuse.api.trace.list(limit=50)
            logger.info(
                f"Retrieved {len(all_traces.data) if hasattr(all_traces, 'data') else 0} traces from Langfuse API"
            )

            trace = None
            if hasattr(all_traces, "data") and all_traces.data:
                # Find our specific trace
                for t in all_traces.data:
                    if hasattr(t, "id") and t.id == trace_id:
                        trace = t
                        logger.info("Found trace %s in list", trace_id)
                        break

            if not trace:
                logger.debug(
                    f"Trace {trace_id} not found in list of {len(all_traces.data) if hasattr(all_traces, 'data') else 0} traces"
                )
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Trace {trace_id} not found, retrying in 3 seconds... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(3)
                    continue
                else:
                    logger.error(
                        f"Trace {trace_id} not found after {max_retries} attempts"
                    )
                    return {}

            # Create evaluation data from trace
            logger.info("Creating evaluation data from trace %s", trace_id)
            eval_data = self._create_evaluation_data(trace)
            if not eval_data:
                logger.error("Could not create evaluation data from trace %s", trace_id)
                return {}

            # Log evaluation data type for debugging
            if hasattr(eval_data, "user_input"):
                if isinstance(eval_data.user_input, str):
                    logger.info(
                        f"Created SingleTurnSample: user_input={eval_data.user_input[:50]}..."
                    )
                else:
                    logger.info(
                        f"Created MultiTurnSample with {len(eval_data.user_input)} messages"
                    )

            # Evaluate all metrics
            logger.info("Starting metric evaluation for trace %s", trace_id)
            scores = await self._evaluate_all_metrics(eval_data)
            logger.info("Metric evaluation completed: %s", scores)

            # Upload scores to Langfuse
            await self._upload_scores_to_langfuse(trace_id, scores)

            logger.info("Evaluation completed for trace %s: %s", trace_id, scores)
            return scores

        return {}

    def _create_evaluation_data(self, trace):
        """
        Transform Langfuse trace data into appropriate Ragas evaluation format.

        Creates either SingleTurnSample or MultiTurnSample based on conversation complexity.
        Extracts conversation history, tool outputs, and metadata for comprehensive evaluation.

        Args:
            trace: Langfuse trace object

        Returns:
            SingleTurnSample, MultiTurnSample, or None on error
        """
        logger.debug("Creating evaluation data from trace: %s", trace.id)
        logger.debug("Trace type: %s", type(trace))

        # Extract original objective from trace metadata
        objective = None

        # Parse trace metadata for original objective
        if hasattr(trace, "metadata") and trace.metadata:
            logger.debug("Trace metadata: %s", trace.metadata)
            metadata = trace.metadata

            # Check if metadata has 'attributes' key (from Strands agent trace attributes)
            if isinstance(metadata, dict) and "attributes" in metadata:
                attrs = metadata["attributes"]
                # Extract the original objective description
                objective = attrs.get("objective.description")

        # Collect conversation history and tool outputs for comprehensive evaluation
        conversation_messages = []
        agent_responses = []
        tool_outputs = []

        # Extract initial objective as first user message
        if objective:
            conversation_messages.append({"role": "user", "content": objective})

        # Extract basic info from trace
        if hasattr(trace, "input") and trace.input:
            logger.debug("Trace input type: %s", type(trace.input))
            logger.debug("Trace input: %s", trace.input)

        if hasattr(trace, "output") and trace.output:
            logger.debug("Trace output type: %s", type(trace.output))
            logger.debug("Trace output: %s...", str(trace.output)[:200])
            agent_responses.append(str(trace.output))
            conversation_messages.append(
                {"role": "assistant", "content": str(trace.output)}
            )

        # Extract detailed conversation flow from observations
        if hasattr(trace, "observations") and trace.observations:
            logger.debug("Trace has %d observations", len(trace.observations))

            for obs in trace.observations:
                if hasattr(obs, "type"):
                    logger.debug(
                        f"Observation type: {obs.type}, name: {getattr(obs, 'name', 'N/A')}"
                    )

                    if obs.type == "GENERATION":
                        if hasattr(obs, "output") and obs.output:
                            response = str(obs.output)
                            agent_responses.append(response)
                            conversation_messages.append(
                                {"role": "assistant", "content": response}
                            )

                    elif obs.type == "SPAN":
                        tool_name = getattr(obs, "name", "").lower()
                        if any(
                            tool in tool_name
                            for tool in [
                                "shell",
                                "http_request",
                                "mem0_memory",
                                "retrieve",
                            ]
                        ):
                            if hasattr(obs, "output") and obs.output:
                                tool_output = f"[{obs.name}] {str(obs.output)[:400]}"
                                tool_outputs.append(tool_output)

        # Determine evaluation format based on conversation complexity
        if len(conversation_messages) > 2:
            # Multi-turn conversation - use MultiTurnSample for agent metrics
            logger.info(
                f"Creating MultiTurnSample with {len(conversation_messages)} messages"
            )

            evaluation_data = MultiTurnSample(
                user_input=conversation_messages,
                reference_topics=[
                    "cybersecurity",
                    "penetration testing",
                    "vulnerability assessment",
                ],
            )
        else:
            # Single-turn or simple interaction - use SingleTurnSample
            user_input = objective
            agent_response = (
                "\n".join(agent_responses[-3:])
                if agent_responses
                else "No agent response captured"
            )
            contexts = (
                tool_outputs[-5:] if tool_outputs else ["No tool outputs captured"]
            )

            logger.info(
                f"Creating SingleTurnSample - user_input: '{user_input[:50]}...', response: '{agent_response[:50]}...', contexts: {len(contexts)}"
            )

            evaluation_data = SingleTurnSample(
                user_input=user_input,
                response=agent_response,
                retrieved_contexts=contexts,
            )

        logger.debug(
            f"Evaluation data created successfully: {evaluation_data.to_dict()}"
        )
        return evaluation_data

    async def _evaluate_all_metrics(self, eval_data) -> Dict[str, float]:
        """Evaluate all configured metrics on evaluation data (SingleTurn or MultiTurn)."""
        scores = {}
        is_multi_turn = isinstance(eval_data, MultiTurnSample)

        logger.info(
            f"Evaluating {len(self.all_metrics)} metrics on {'MultiTurn' if is_multi_turn else 'SingleTurn'} sample"
        )

        if is_multi_turn:
            logger.debug(
                f"MultiTurn evaluation data: {len(eval_data.user_input)} messages, topics: {eval_data.reference_topics}"
            )
        else:
            logger.debug(
                f"SingleTurn evaluation data: user_input='{eval_data.user_input[:100]}...', response='{eval_data.response[:100]}...', contexts={len(eval_data.retrieved_contexts)}"
            )

        for metric in self.all_metrics:
            logger.info("Starting evaluation of metric: %s", metric.name)

            # Determine appropriate evaluation method based on data type and metric capabilities
            if is_multi_turn and hasattr(metric, "multi_turn_ascore"):
                # Use multi-turn evaluation for agent-specific metrics
                score = await metric.multi_turn_ascore(eval_data)
            elif not is_multi_turn and hasattr(metric, "single_turn_ascore"):
                # Use single-turn evaluation for RAG and response metrics
                score = await metric.single_turn_ascore(eval_data)
            else:
                # Handle metrics that don't support the current data type
                if is_multi_turn:
                    logger.warning(
                        f"Metric {metric.name} doesn't support multi-turn evaluation, skipping"
                    )
                    scores[metric.name] = 0.0
                    continue
                logger.error("Metric %s missing evaluation method", metric.name)
                scores[metric.name] = 0.0
                continue

            logger.debug("Raw score for %s: %s (type: %s)", metric.name, score, type(score))

            if score is None:
                logger.warning("Score is None for %s", metric.name)
                scores[metric.name] = 0.0
            else:
                scores[metric.name] = float(score)
                logger.info("Metric %s score: %s", metric.name, scores[metric.name])

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
                    comment=f"Automated ragas evaluation: {metric_name} ({metric_category})",
                    metadata=score_metadata,
                )
            elif hasattr(self.langfuse, "create_score"):
                self.langfuse.create_score(
                    trace_id=trace_id,
                    name=metric_name,
                    value=score,
                    comment=f"Automated ragas evaluation: {metric_name} ({metric_category})",
                    metadata=score_metadata,
                )
            else:
                logger.error("No score creation method found on Langfuse client")
                return

        logger.info(
            f"Uploaded {len(scores)} evaluation scores to Langfuse trace {trace_id}"
        )

        # Flush to ensure scores are sent
        self.langfuse.flush()

    def _get_metric_category(self, metric_name: str) -> str:
        """Categorize metrics for better organization in Langfuse."""
        # TODO: adding metric tags in the future for advanced filtering
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
