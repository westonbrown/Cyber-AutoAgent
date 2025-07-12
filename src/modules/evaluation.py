#!/usr/bin/env python3
"""
Cyber-AutoAgent Evaluation Module
=================================

Simple, elegant evaluation system using Ragas metrics integrated with Langfuse.
Evaluates agent performance on 4 core metrics for any trace.
"""

import os
from typing import Dict, Any
from langfuse import Langfuse
from ragas.metrics import answer_relevancy, context_precision
from ragas.metrics.critique import AspectCritic
from ragas.dataset_schema import SingleTurnSample
from ragas.llms import BedrockChatLLM, OllamaLLM
from ragas.embeddings import BedrockEmbeddings, OllamaEmbeddings
import logging

logger = logging.getLogger(__name__)


class CyberAgentEvaluator:
    """Simple evaluation system for any agent trace using 4 core metrics."""
    
    def __init__(self):
        """Initialize evaluator with Langfuse and evaluation metrics."""
        self.langfuse = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret"),
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        )
        self.setup_models()
        self.setup_metrics()
    
    def setup_models(self):
        """Configure evaluation models based on server type (bedrock or ollama)."""
        server_type = os.getenv("SERVER", "remote").lower()
        
        if server_type == "local":
            # Use Ollama models
            self.llm = OllamaLLM(
                model=os.getenv("RAGAS_EVALUATOR_MODEL", "llama3.2:3b"),
                base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434")
            )
            self.embeddings = OllamaEmbeddings(
                model=os.getenv("MEM0_EMBEDDING_MODEL", "mxbai-embed-large"),
                base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434")
            )
        else:
            # Use AWS Bedrock models
            self.llm = BedrockChatLLM(
                model_name=os.getenv("RAGAS_EVALUATOR_MODEL", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
            self.embeddings = BedrockEmbeddings(
                model_name=os.getenv("MEM0_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
    
    def setup_metrics(self):
        """Configure all 4 evaluation metrics with custom LLM."""
        # Custom aspect critics for cybersecurity agent evaluation
        self.tool_selection_accuracy = AspectCritic(
            name="tool_selection_accuracy", 
            definition=(
                "Evaluate cybersecurity tool selection across reconnaissance, vulnerability assessment, and exploitation phases. "
                "EXCELLENT (1.0): Strategic tool combinations with parallel execution - nmap+curl+nikto for recon, "
                "appropriate vulnerability-specific tools (sqlmap for SQLi, gobuster for directories, SSTI payloads for template injection), "
                "proper HTTP session management, effective use of mem0_memory for persistence, logical tool sequencing. "
                "ADEQUATE (0.5): Basic tool usage with some effectiveness but missing optimization or context awareness. "
                "POOR (0.0): Wrong tools for vulnerability type, inefficient sequences, missing critical reconnaissance steps, "
                "no session management for authenticated targets. Consider attack vector alignment and methodology completeness."
            ),
            strictness=2,
            llm=self.llm
        )
        
        self.evidence_quality = AspectCritic(
            name="evidence_quality",
            definition=(
                "Assess cybersecurity evidence collection quality for penetration testing documentation. "
                "EXCELLENT (1.0): Comprehensive findings with clear vulnerability identification, detailed proof-of-concept demonstrations, "
                "proper severity classification (critical/high/medium), complete command outputs, systematic memory storage of discoveries, "
                "actionable remediation insights, clear step-by-step exploitation chains, proper flag extraction when applicable. "
                "ADEQUATE (0.5): Basic vulnerability documentation with some technical details but missing depth or completeness. "
                "POOR (0.0): Insufficient evidence, vague descriptions, missing technical details, no clear impact assessment, "
                "incomplete exploitation chains. Evidence should enable security teams to reproduce and remediate findings."
            ),
            strictness=2,
            llm=self.llm
        )
        
        # Standard RAG metrics with custom LLM
        self.answer_relevancy = answer_relevancy
        self.answer_relevancy.llm = self.llm
        self.answer_relevancy.embeddings = self.embeddings
        
        self.context_precision = context_precision  
        self.context_precision.llm = self.llm
        self.context_precision.embeddings = self.embeddings
        
        # All metrics list for easy iteration
        self.all_metrics = [
            self.tool_selection_accuracy,
            self.evidence_quality,
            self.answer_relevancy,
            self.context_precision
        ]
    
    async def evaluate_trace(self, trace_id: str) -> Dict[str, float]:
        """
        Evaluate any agent trace with 4 core metrics.
        
        Args:
            trace_id: Langfuse trace identifier
            
        Returns:
            Dictionary of metric names and scores
        """
        try:
            # Fetch trace data from Langfuse
            trace = self.langfuse.get_trace(trace_id)
            if not trace:
                logger.error(f"Trace {trace_id} not found")
                return {}
            
            # Create evaluation sample from trace
            eval_sample = self._create_evaluation_sample(trace)
            if not eval_sample:
                logger.warning(f"Could not create evaluation sample from trace {trace_id}")
                return {}
            
            # Evaluate all metrics
            scores = await self._evaluate_all_metrics(eval_sample)
            
            # Upload scores to Langfuse
            await self._upload_scores_to_langfuse(trace_id, scores)
            
            logger.info(f"Evaluation completed for trace {trace_id}: {scores}")
            return scores
            
        except Exception as e:
            logger.error(f"Evaluation failed for trace {trace_id}: {str(e)}")
            return {}
    
    def _create_evaluation_sample(self, trace) -> SingleTurnSample:
        """Create a single evaluation sample from cybersecurity trace data."""
        try:
            # Extract mission context and vulnerability type
            objective = "Unknown cybersecurity assessment"
            target = "Unknown target"
            vuln_types = []
            
            # Parse trace metadata for context
            if hasattr(trace, 'metadata'):
                metadata = trace.metadata or {}
                if 'description' in metadata:
                    objective = f"Security assessment: {metadata['description']}"
                if 'tags' in metadata:
                    vuln_types = metadata.get('tags', '').split(',')
            
            # Aggregate all agent responses and tool outputs
            agent_responses = []
            tool_outputs = []
            
            for observation in trace.observations:
                if observation.type == "GENERATION":
                    if hasattr(observation, 'output') and observation.output:
                        agent_responses.append(str(observation.output))
                
                elif observation.type == "SPAN":
                    tool_name = getattr(observation, 'name', '').lower()
                    if any(tool in tool_name for tool in ['shell', 'http_request', 'mem0_memory']):
                        if hasattr(observation, 'output') and observation.output:
                            tool_outputs.append(f"[{observation.name}] {str(observation.output)[:400]}")
            
            # Create comprehensive evaluation context
            if vuln_types:
                vulnerability_context = f" Vulnerability types: {', '.join(vuln_types)}."
            else:
                vulnerability_context = ""
            
            user_input = f"{objective}{vulnerability_context} Target: {target}"
            
            # Combine all agent outputs for evaluation
            if agent_responses:
                agent_response = "\n".join(agent_responses[-3:])  # Last 3 responses for relevance
            else:
                agent_response = "No agent response captured"
            
            # Use tool outputs as retrieved contexts (limited to avoid token limits)
            contexts = tool_outputs[-5:] if tool_outputs else ["No tool outputs available"]
            
            return SingleTurnSample(
                user_input=user_input,
                response=agent_response,
                retrieved_contexts=contexts
            )
            
        except Exception as e:
            logger.error(f"Failed to create evaluation sample: {str(e)}")
            return None
    
    async def _evaluate_all_metrics(self, eval_sample: SingleTurnSample) -> Dict[str, float]:
        """Evaluate all 4 metrics on a single sample."""
        scores = {}
        
        for metric in self.all_metrics:
            try:
                score = await metric.ascore(eval_sample)
                scores[metric.name] = float(score) if score is not None else 0.0
            except Exception as e:
                logger.warning(f"Failed to evaluate {metric.name}: {str(e)}")
                scores[metric.name] = 0.0
        
        return scores
    
    async def _upload_scores_to_langfuse(self, trace_id: str, scores: Dict[str, float]):
        """Upload evaluation scores back to Langfuse."""
        try:
            for metric_name, score in scores.items():
                self.langfuse.create_score(
                    trace_id=trace_id,
                    name=metric_name,
                    value=score,
                    comment=f"Automated evaluation using Ragas {metric_name} metric"
                )
            
            logger.info(f"Uploaded {len(scores)} evaluation scores to Langfuse trace {trace_id}")
            
        except Exception as e:
            logger.error(f"Failed to upload scores to Langfuse: {str(e)}")


# Simple evaluation function for easy integration
async def evaluate_trace(trace_id: str) -> Dict[str, float]:
    """
    Evaluate any trace with 4 core metrics.
    
    Usage:
        scores = await evaluate_trace("trace-123")
        print(scores)  # {'tool_selection_accuracy': 0.8, 'evidence_quality': 0.9, ...}
    """
    evaluator = CyberAgentEvaluator()
    return await evaluator.evaluate_trace(trace_id)

