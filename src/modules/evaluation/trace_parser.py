#!/usr/bin/env python3
"""
Trace Parser for Cyber-AutoAgent Evaluation
==========================================

Provides robust parsing of Langfuse traces to extract meaningful data
for evaluation metrics. Handles various trace formats and ensures
data quality for accurate metric computation.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from ragas.dataset_schema import MultiTurnSample, SingleTurnSample

logger = logging.getLogger(__name__)


@dataclass
class ParsedMessage:
    """Represents a parsed message from trace data."""
    role: str
    content: str
    timestamp: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedToolCall:
    """Represents a parsed tool call from trace data."""
    name: str
    input_data: Dict[str, Any]
    output: Optional[str] = None
    success: bool = True
    timestamp: Optional[float] = None


@dataclass
class ParsedTrace:
    """Represents fully parsed trace data ready for evaluation."""
    trace_id: str
    trace_name: str
    objective: str
    messages: List[ParsedMessage]
    tool_calls: List[ParsedToolCall]
    final_output: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_multi_turn(self) -> bool:
        """Determine if this trace represents a multi-turn conversation."""
        # Count substantial messages (not just tool outputs)
        substantial_messages = [
            msg for msg in self.messages 
            if msg.role in ["user", "assistant"] and len(msg.content) > 50
        ]
        return len(substantial_messages) > 2
    
    @property
    def has_tool_usage(self) -> bool:
        """Check if the trace includes tool usage."""
        return len(self.tool_calls) > 0
    
    def get_tool_outputs(self, limit: int = 10) -> List[str]:
        """Get formatted tool outputs for context."""
        outputs = []
        for tool in self.tool_calls[-limit:]:
            if tool.output:
                output_preview = tool.output[:500] if len(tool.output) > 500 else tool.output
                outputs.append(f"[{tool.name}] {output_preview}")
        return outputs


class TraceParser:
    """
    Robust parser for extracting evaluation data from Langfuse traces.
    
    Handles multiple trace formats and ensures data quality for metrics.
    """
    
    def __init__(self):
        """Initialize the trace parser."""
        self.security_tools = {
            "shell", "http_request", "mem0_memory", "editor", 
            "load_tool", "swarm", "stop"
        }
        
    def parse_trace(self, trace: Any) -> Optional[ParsedTrace]:
        """
        Parse a Langfuse trace into structured data for evaluation.
        
        Args:
            trace: Raw Langfuse trace object
            
        Returns:
            ParsedTrace object or None if parsing fails
        """
        try:
            # Extract basic trace information
            trace_id = getattr(trace, "id", "unknown")
            trace_name = getattr(trace, "name", "Unknown Trace")
            
            logger.debug(f"Parsing trace: {trace_id} - {trace_name}")
            
            # Extract objective from metadata
            objective = self._extract_objective(trace)
            if not objective:
                logger.warning(f"No objective found for trace {trace_id}")
                objective = "Security assessment"
            
            # Parse messages and tool calls
            messages = self._extract_messages(trace)
            tool_calls = self._extract_tool_calls(trace)
            
            # Get final output
            final_output = self._extract_final_output(trace)
            
            # Build metadata
            metadata = self._extract_metadata(trace)
            
            parsed_trace = ParsedTrace(
                trace_id=trace_id,
                trace_name=trace_name,
                objective=objective,
                messages=messages,
                tool_calls=tool_calls,
                final_output=final_output,
                metadata=metadata
            )
            
            logger.info(
                f"Successfully parsed trace {trace_id}: "
                f"{len(messages)} messages, {len(tool_calls)} tool calls, "
                f"multi_turn={parsed_trace.is_multi_turn}"
            )
            
            return parsed_trace
            
        except Exception as e:
            logger.error(f"Error parsing trace: {e}", exc_info=True)
            return None
    
    def _extract_objective(self, trace: Any) -> Optional[str]:
        """Extract the assessment objective from trace metadata."""
        # Try multiple locations where objective might be stored
        
        # Method 1: Direct metadata attributes
        if hasattr(trace, "metadata") and trace.metadata:
            metadata = trace.metadata
            if isinstance(metadata, dict):
                # Check attributes for objective
                if "attributes" in metadata:
                    attrs = metadata["attributes"]
                    if isinstance(attrs, dict):
                        objective = attrs.get("objective.description")
                        if objective:
                            return objective
                
                # Check direct objective field
                objective = metadata.get("objective")
                if objective:
                    return objective
        
        # Method 2: Parse from input
        if hasattr(trace, "input") and trace.input:
            input_str = str(trace.input)
            if "objective" in input_str.lower():
                # Try to extract objective from input
                try:
                    input_data = json.loads(input_str) if isinstance(input_str, str) else input_str
                    if isinstance(input_data, dict):
                        return input_data.get("objective")
                except:
                    pass
        
        # Method 3: Extract from trace name
        if hasattr(trace, "name") and trace.name:
            # Pattern: "Security Assessment - <target> - <operation_id>"
            if " - " in trace.name:
                parts = trace.name.split(" - ")
                if len(parts) >= 2:
                    return f"Security assessment of {parts[1]}"
        
        return None
    
    def _extract_messages(self, trace: Any) -> List[ParsedMessage]:
        """Extract conversation messages from trace."""
        messages = []
        
        # Don't add objective as a separate message - it will be used directly
        # This prevents duplication in the evaluation data
        
        # Extract messages from observations
        if hasattr(trace, "observations") and trace.observations:
            for obs in trace.observations:
                message = self._parse_observation_message(obs)
                if message:
                    messages.append(message)
        
        # Extract from direct output if no observations
        if not messages and hasattr(trace, "output") and trace.output:
            messages.append(ParsedMessage(
                role="assistant",
                content=str(trace.output),
                metadata={"source": "trace_output"}
            ))
        
        return messages
    
    def _parse_observation_message(self, obs: Any) -> Optional[ParsedMessage]:
        """Parse a single observation into a message if applicable."""
        obs_type = getattr(obs, "type", "")
        
        # Handle GENERATION type (LLM responses)
        if obs_type == "GENERATION":
            if hasattr(obs, "output") and obs.output:
                content = self._extract_content_from_output(obs.output)
                if content:
                    return ParsedMessage(
                        role="assistant",
                        content=content,
                        timestamp=getattr(obs, "startTime", None),
                        metadata={
                            "observation_id": getattr(obs, "id", ""),
                            "model": getattr(obs, "model", ""),
                        }
                    )
        
        # Handle EVENT type (user inputs)
        elif obs_type == "EVENT":
            if hasattr(obs, "input") and obs.input:
                content = str(obs.input)
                if content and len(content) > 10:
                    return ParsedMessage(
                        role="user",
                        content=content,
                        timestamp=getattr(obs, "startTime", None),
                        metadata={"observation_id": getattr(obs, "id", "")}
                    )
        
        return None
    
    def _extract_content_from_output(self, output: Any) -> Optional[str]:
        """Extract readable content from various output formats."""
        if isinstance(output, str):
            return output
        
        if isinstance(output, dict):
            # Handle structured message format
            if "content" in output:
                content = output["content"]
                if isinstance(content, list):
                    # Extract text from content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    return "\n".join(text_parts)
                else:
                    return str(content)
            
            # Handle direct text field
            if "text" in output:
                return str(output["text"])
            
            # Handle message field
            if "message" in output:
                return str(output["message"])
        
        # Fallback to string representation
        output_str = str(output)
        if output_str and len(output_str) > 10:
            return output_str
        
        return None
    
    def _extract_tool_calls(self, trace: Any) -> List[ParsedToolCall]:
        """Extract tool calls from trace observations."""
        tool_calls = []
        
        if hasattr(trace, "observations") and trace.observations:
            for obs in trace.observations:
                if obs.type == "SPAN":
                    tool_call = self._parse_tool_observation(obs)
                    if tool_call:
                        tool_calls.append(tool_call)
        
        return tool_calls
    
    def _parse_tool_observation(self, obs: Any) -> Optional[ParsedToolCall]:
        """Parse a SPAN observation into a tool call."""
        name = getattr(obs, "name", "").lower()
        
        # Check if this is a security tool
        if any(tool in name for tool in self.security_tools):
            # Extract input data
            input_data = {}
            if hasattr(obs, "input") and obs.input:
                if isinstance(obs.input, dict):
                    input_data = obs.input
                else:
                    input_data = {"raw_input": str(obs.input)}
            
            # Extract output
            output = None
            if hasattr(obs, "output") and obs.output:
                output = str(obs.output)
            
            return ParsedToolCall(
                name=name,
                input_data=input_data,
                output=output,
                success=getattr(obs, "statusMessage", None) != "error",
                timestamp=getattr(obs, "startTime", None)
            )
        
        return None
    
    def _extract_final_output(self, trace: Any) -> Optional[str]:
        """Extract the final output from the trace."""
        if hasattr(trace, "output") and trace.output:
            return self._extract_content_from_output(trace.output)
        return None
    
    def _extract_metadata(self, trace: Any) -> Dict[str, Any]:
        """Extract relevant metadata from the trace."""
        metadata = {}
        
        if hasattr(trace, "metadata") and isinstance(trace.metadata, dict):
            metadata.update(trace.metadata)
        
        # Add computed metrics
        if hasattr(trace, "latency"):
            metadata["latency_ms"] = trace.latency
        
        if hasattr(trace, "tokenUsage") and trace.tokenUsage:
            metadata["token_usage"] = {
                "input": getattr(trace.tokenUsage, "input", 0),
                "output": getattr(trace.tokenUsage, "output", 0),
                "total": getattr(trace.tokenUsage, "total", 0),
            }
        
        return metadata
    
    def create_evaluation_sample(
        self, parsed_trace: ParsedTrace
    ) -> Union[SingleTurnSample, MultiTurnSample]:
        """
        Create appropriate Ragas evaluation sample from parsed trace.
        
        Args:
            parsed_trace: Parsed trace data
            
        Returns:
            SingleTurnSample or MultiTurnSample for evaluation
        """
        if parsed_trace.is_multi_turn:
            return self._create_multi_turn_sample(parsed_trace)
        else:
            return self._create_single_turn_sample(parsed_trace)
    
    def _create_single_turn_sample(self, parsed_trace: ParsedTrace) -> SingleTurnSample:
        """Create a SingleTurnSample for simple evaluations."""
        # Get user input (objective or first user message)
        user_input = parsed_trace.objective
        
        # Get agent response (final output or concatenated assistant messages)
        if parsed_trace.final_output:
            response = parsed_trace.final_output
        else:
            assistant_messages = [
                msg.content for msg in parsed_trace.messages 
                if msg.role == "assistant"
            ]
            response = "\n\n".join(assistant_messages[-3:]) if assistant_messages else ""
        
        # Get tool outputs as contexts
        contexts = parsed_trace.get_tool_outputs(limit=10)
        
        # Ensure we have meaningful data
        if not response:
            response = "No agent response captured"
        if not contexts:
            contexts = ["No tool outputs captured"]
        
        logger.debug(
            f"Created SingleTurnSample: "
            f"input_len={len(user_input)}, "
            f"response_len={len(response)}, "
            f"contexts={len(contexts)}"
        )
        
        return SingleTurnSample(
            user_input=user_input,
            response=response,
            retrieved_contexts=contexts
        )
    
    def _create_multi_turn_sample(self, parsed_trace: ParsedTrace) -> MultiTurnSample:
        """Create a MultiTurnSample for complex conversation evaluations."""
        # Convert messages to conversation format
        conversation = []
        
        for msg in parsed_trace.messages:
            conversation.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Add tool outputs as system messages
        for tool in parsed_trace.tool_calls:
            if tool.output:
                conversation.append({
                    "role": "system",
                    "content": f"Tool [{tool.name}]: {tool.output[:200]}..."
                })
        
        logger.debug(
            f"Created MultiTurnSample: "
            f"{len(conversation)} messages, "
            f"{len(parsed_trace.tool_calls)} tool calls"
        )
        
        return MultiTurnSample(
            user_input=conversation,
            reference_topics=[
                "cybersecurity",
                "penetration testing",
                "vulnerability assessment",
                "security tools",
                "exploitation"
            ]
        )