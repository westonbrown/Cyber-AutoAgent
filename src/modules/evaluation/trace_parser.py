#!/usr/bin/env python3
"""
Trace Parser for Cyber-AutoAgent Evaluation
==========================================

Provides robust parsing of Langfuse traces to extract meaningful data
for evaluation metrics. Handles various trace formats and ensures
data quality for accurate metric computation.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ragas.dataset_schema import MultiTurnSample, SingleTurnSample

from modules.config.system.logger import get_logger

logger = get_logger("Evaluation.TraceParser")


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
        """Determine if this trace represents a multi-turn conversation.

        For cybersecurity assessments, we consider it multi-turn if:
        - Has 2+ tool calls (shows interaction)
        - Has 3+ messages of any length
        - Has substantial back-and-forth dialogue
        """
        # Tool-based operations are inherently multi-turn
        if len(self.tool_calls) >= 2:
            logger.debug(f"Classified as multi-turn: {len(self.tool_calls)} tool calls")
            return True

        # Multiple messages indicate conversation
        if len(self.messages) >= 3:
            logger.debug(f"Classified as multi-turn: {len(self.messages)} messages")
            return True

        # Check for substantial dialogue
        substantial_messages = [
            msg
            for msg in self.messages
            if msg.role in ["user", "assistant"] and len(msg.content) > 30
        ]

        if len(substantial_messages) >= 2:
            logger.debug(
                f"Classified as multi-turn: {len(substantial_messages)} substantial messages"
            )
            return True

        logger.debug(
            f"Classified as single-turn: tools={len(self.tool_calls)}, msgs={len(self.messages)}"
        )
        return False

    @property
    def has_tool_usage(self) -> bool:
        """Check if the trace includes tool usage."""
        return len(self.tool_calls) > 0

    def get_tool_outputs(self, limit: int = 10) -> List[str]:
        """Get formatted tool outputs for context."""
        outputs = []
        for tool in self.tool_calls[-limit:]:
            if tool.output:
                # Clean and format output for better context
                output_str = str(tool.output).strip()
                if output_str and output_str != "None":
                    # Limit length but preserve meaningful content
                    output_preview = (
                        output_str[:800] if len(output_str) > 800 else output_str
                    )
                    # Format with tool name and key details
                    formatted = f"Tool [{tool.name}]: {output_preview}"
                    outputs.append(formatted)
            elif tool.input_data:
                # Include input if no output for context
                input_str = str(tool.input_data).strip()[:200]
                outputs.append(f"Tool [{tool.name}] executed: {input_str}")
        return outputs


class TraceParser:
    """
    Robust parser for extracting evaluation data from Langfuse traces.

    Handles multiple trace formats and ensures data quality for metrics.
    """

    def __init__(self, llm=None, langfuse_client=None):
        """Initialize the trace parser.

        Args:
            llm: Optional LLM instance for generating reference topics
            langfuse_client: Langfuse client for fetching observations
        """
        self.security_tools = {
            "shell",
            "http_request",
            "mem0_memory",
            "editor",
            "load_tool",
            "swarm",
            "stop",
        }
        self.llm = llm
        self.langfuse = langfuse_client

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

            logger.debug("Parsing trace: %s - %s", trace_id, trace_name)

            # Extract objective from metadata
            objective = self._extract_objective(trace)
            if not objective:
                logger.warning("No objective found for trace %s", trace_id)
                objective = "Security assessment"

            # Fetch actual observations from Langfuse if needed
            observations = self._fetch_observations(trace)

            # Parse messages and tool calls from observations
            messages = self._extract_messages(trace, observations)
            tool_calls = self._extract_tool_calls(trace, observations)

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
                metadata=metadata,
            )

            logger.info(
                "Successfully parsed trace %s: %d messages, %d tool calls, multi_turn=%s",
                trace_id,
                len(messages),
                len(tool_calls),
                parsed_trace.is_multi_turn,
            )

            return parsed_trace

        except Exception as e:
            logger.error("Error parsing trace: %s", e, exc_info=True)
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
            # Try structured parse first
            if "objective" in input_str.lower():
                try:
                    input_data = (
                        json.loads(input_str)
                        if isinstance(input_str, str)
                        else input_str
                    )
                    if isinstance(input_data, dict):
                        obj = input_data.get("objective")
                        if obj:
                            return obj
                except Exception:
                    # Fall back to regex extraction from free-form content
                    pass
            # Handle list-of-messages with nested content (common in Langfuse traces)
            try:
                if isinstance(trace.input, list) and trace.input:
                    first = trace.input[0]
                    content = None
                    # Newer formats: list of dicts with content
                    if isinstance(first, dict) and "content" in first:
                        content = str(first.get("content", ""))
                    else:
                        content = input_str
                    if content:
                        import re

                        m = re.search(
                            r"Objective:\s*(.+)", content, flags=re.IGNORECASE
                        )
                        if m:
                            return m.group(1).strip()
            except Exception:
                pass

        # Method 3: Extract from trace name
        if hasattr(trace, "name") and trace.name:
            # Pattern: "Security Assessment - <target> - <operation_id>"
            if " - " in trace.name:
                parts = trace.name.split(" - ")
                if len(parts) >= 2:
                    return f"Security assessment of {parts[1]}"

        return None

    def _fetch_observations(self, trace: Any) -> List[Any]:
        """Fetch actual observation objects from Langfuse.

        Args:
            trace: Trace object containing observation IDs

        Returns:
            List of observation objects
        """
        observations = []

        # Check if we have observation IDs to fetch
        if hasattr(trace, "observations") and trace.observations:
            # Check if first item is already an object or just an ID
            first_obs = trace.observations[0] if trace.observations else None

            if first_obs and hasattr(first_obs, "type"):
                # Already have observation objects
                return trace.observations

            # Need to fetch observations from Langfuse
            if self.langfuse and trace.observations:
                for obs_id in trace.observations:
                    try:
                        # Fetch observation from Langfuse API
                        obs = self.langfuse.api.observations.get(obs_id)
                        if obs:
                            observations.append(obs)
                    except Exception as e:
                        logger.warning(f"Failed to fetch observation {obs_id}: {e}")

        return observations

    def _extract_messages(
        self, trace: Any, observations: List[Any]
    ) -> List[ParsedMessage]:
        """Extract conversation messages from trace."""
        messages = []

        # Add the objective as initial user message for context
        objective = self._extract_objective(trace)
        if objective:
            messages.append(
                ParsedMessage(
                    role="user", content=objective, metadata={"source": "objective"}
                )
            )

        # Extract messages from fetched observations
        for obs in observations:
            message = self._parse_observation_message(obs)
            if message:
                messages.append(message)

                # Also extract tool interactions as messages for richer context
                if getattr(obs, "type", "") == "SPAN":
                    tool_msg = self._extract_tool_as_message(obs)
                    if tool_msg:
                        messages.append(tool_msg)

        # Extract from input if available
        if hasattr(trace, "input") and trace.input:
            input_str = str(trace.input)
            if (
                input_str
                and len(input_str) > 20
                and not any(m.content == input_str for m in messages)
            ):
                messages.append(
                    ParsedMessage(
                        role="user",
                        content=input_str,
                        metadata={"source": "trace_input"},
                    )
                )

        # Extract from direct output if we have few messages
        if len(messages) < 2 and hasattr(trace, "output") and trace.output:
            output_content = self._extract_content_from_output(trace.output)
            if output_content:
                messages.append(
                    ParsedMessage(
                        role="assistant",
                        content=output_content,
                        metadata={"source": "trace_output"},
                    )
                )

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
                        },
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
                        metadata={"observation_id": getattr(obs, "id", "")},
                    )

        return None

    def _extract_reference_topics(self, parsed_trace: ParsedTrace) -> List[str]:
        """Extract reference topics based on the operation objective."""
        topics = []

        if parsed_trace.objective:
            topics.append(parsed_trace.objective)

        return topics

    def _extract_tool_as_message(self, obs: Any) -> Optional[ParsedMessage]:
        """Extract tool call as a message for evaluation context."""
        name = getattr(obs, "name", "").lower()

        # Only include security-relevant tools
        if not any(tool in name for tool in self.security_tools):
            return None

        obs_input = getattr(obs, "input", None)
        obs_output = getattr(obs, "output", None)

        if obs_input or obs_output:
            # Format tool interaction as a message
            content_parts = []
            if obs_input:
                input_str = str(obs_input)[:500]  # Limit length
                content_parts.append(f"Tool {name} called with: {input_str}")
            if obs_output:
                output_str = str(obs_output)[:500]  # Limit length
                content_parts.append(f"Tool output: {output_str}")

            if content_parts:
                return ParsedMessage(
                    role="system",
                    content=" | ".join(content_parts),
                    timestamp=getattr(obs, "startTime", None),
                    metadata={"tool": name, "source": "tool_interaction"},
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

    def _extract_tool_calls(
        self, trace: Any, observations: List[Any]
    ) -> List[ParsedToolCall]:
        """Extract tool calls from fetched observations.

        Args:
            trace: Original trace object
            observations: List of fetched observation objects

        Returns:
            List of parsed tool calls
        """
        tool_calls = []

        for obs in observations:
            # Check observation type
            obs_type = (
                obs.get("type") if isinstance(obs, dict) else getattr(obs, "type", None)
            )

            # Look for TOOL type (Langfuse uses "TOOL" for tool calls)
            if obs_type == "TOOL":
                tool_call = self._parse_tool_observation(obs)
                if tool_call:
                    tool_calls.append(tool_call)

            # Also check SPAN type which Strands SDK uses for tool invocations
            elif obs_type == "SPAN":
                obs_name = (
                    obs.get("name", "")
                    if isinstance(obs, dict)
                    else getattr(obs, "name", "")
                )
                # Strands tool invocations have names like "Tool: mem0_memory" or "execute_tool"
                if obs_name and (
                    "Tool:" in obs_name
                    or "execute_tool" in obs_name.lower()
                    or any(tool in obs_name.lower() for tool in self.security_tools)
                ):
                    tool_call = self._parse_tool_observation(obs)
                    if tool_call and tool_call not in tool_calls:
                        tool_calls.append(tool_call)

            # Also check if name contains tool indicators regardless of type
            obs_name = (
                obs.get("name", "")
                if isinstance(obs, dict)
                else getattr(obs, "name", "")
            )
            if obs_name:
                # Check for execute_tool or tool names in the observation name
                if "execute_tool" in obs_name.lower() or any(
                    tool in obs_name.lower() for tool in self.security_tools
                ):
                    if obs_type not in ["TOOL", "SPAN"]:  # Avoid duplicates
                        tool_call = self._parse_tool_observation(obs)
                        if tool_call and tool_call not in tool_calls:
                            tool_calls.append(tool_call)

        logger.debug(
            f"Extracted {len(tool_calls)} tool calls from {len(observations)} observations"
        )
        return tool_calls

    def _parse_tool_observation(self, obs: Any) -> Optional[ParsedToolCall]:
        """Parse a TOOL observation into a tool call.

        Args:
            obs: Observation object from Langfuse

        Returns:
            ParsedToolCall or None
        """
        # Extract observation details
        if isinstance(obs, dict):
            name = obs.get("name", "")
            obs_input = obs.get("input")
            obs_output = obs.get("output")
            timestamp = obs.get("startTime", None)
            status_msg = obs.get("statusMessage")
        else:
            name = getattr(obs, "name", "")
            obs_input = getattr(obs, "input", None)
            obs_output = getattr(obs, "output", None)
            timestamp = getattr(obs, "startTime", None)
            status_msg = getattr(obs, "statusMessage", None)

        # Extract tool name from observation name
        # Strands SDK format: "Tool: tool_name" or legacy format: "execute_tool <tool_name>"
        if "Tool:" in name:
            tool_name = name.split("Tool:")[-1].strip().lower()
        elif "execute_tool" in name.lower():
            tool_name = name.replace("execute_tool", "").strip().lower()
        else:
            # Direct tool name
            tool_name = name.strip().lower()

        # Parse input data
        input_data = {}
        if obs_input:
            if isinstance(obs_input, list) and obs_input:
                # Input is often a list with role/content structure
                first_input = obs_input[0]
                if isinstance(first_input, dict):
                    if "content" in first_input:
                        content = first_input["content"]
                        # Try to parse as JSON
                        try:
                            import json

                            input_data = (
                                json.loads(content)
                                if isinstance(content, str)
                                else content
                            )
                        except (json.JSONDecodeError, TypeError):
                            input_data = {"raw_input": str(content)}
                    elif "role" in first_input and first_input.get("role") == "tool":
                        # Tool input format
                        input_data = {"raw_input": str(first_input)}
                else:
                    input_data = {"raw_input": str(obs_input)}
            elif isinstance(obs_input, dict):
                input_data = obs_input
            else:
                input_data = {"raw_input": str(obs_input) if obs_input else ""}

        # Parse output
        output = None
        if obs_output:
            if isinstance(obs_output, dict):
                if "message" in obs_output:
                    output = obs_output["message"]
                elif "text" in obs_output:
                    output = obs_output["text"]
                else:
                    output = str(obs_output)
            elif isinstance(obs_output, list) and obs_output:
                # Output might be a list of messages
                first_output = obs_output[0]
                if isinstance(first_output, dict) and "text" in first_output:
                    output = first_output["text"]
                else:
                    output = str(obs_output)
            else:
                output = str(obs_output) if obs_output else None

        # Determine success status
        success = status_msg != "error" if status_msg else True

        # Check if this is a valid tool
        if tool_name and (
            any(tool in tool_name for tool in self.security_tools)
            or "build_report" in tool_name
            or "specialized_recon" in tool_name
            or "advanced_payload" in tool_name
            or "auth_chain" in tool_name
        ):
            return ParsedToolCall(
                name=tool_name,
                input_data=input_data,
                output=output,
                success=success,
                timestamp=timestamp,
            )

        return None

    def _extract_final_output(self, trace: Any) -> Optional[str]:
        """Extract the final output from the trace."""
        if hasattr(trace, "output") and trace.output:
            return self._extract_content_from_output(trace.output)
        return None

    def count_memory_operations(self, tool_calls: List[ParsedToolCall]) -> int:
        """Count memory operations from tool calls.

        Args:
            tool_calls: List of parsed tool calls

        Returns:
            Number of memory operations
        """
        return sum(1 for tc in tool_calls if tc.name == "mem0_memory")

    def count_evidence_findings(self, tool_calls: List[ParsedToolCall]) -> int:
        """Count evidence findings stored in memory.

        Args:
            tool_calls: List of parsed tool calls

        Returns:
            Number of evidence findings
        """
        findings = 0
        for tc in tool_calls:
            if tc.name == "mem0_memory" and tc.input_data:
                input_str = str(tc.input_data).lower()
                # Check for finding indicators in the memory store
                if (
                    "finding" in input_str
                    or "vulnerability" in input_str
                    or "critical" in input_str
                ):
                    # Validate it's actually a store operation with evidence
                    if "action" in input_str and "store" in input_str:
                        findings += 1
        return findings

    def _extract_metadata(self, trace: Any) -> Dict[str, Any]:
        """Extract relevant metadata from the trace."""
        metadata: Dict[str, Any] = {}

        if hasattr(trace, "metadata") and isinstance(trace.metadata, dict):
            metadata.update(trace.metadata)

        # Try to attach session/operation identifiers for downstream filtering
        try:
            if hasattr(trace, "session_id") and trace.session_id:
                metadata.setdefault("session_id", trace.session_id)
            # Flatten attributes.operation.id if present
            attrs = metadata.get("attributes") if isinstance(metadata, dict) else None
            if isinstance(attrs, dict):
                op_id = attrs.get("operation.id") or attrs.get("langfuse.session.id")
                if op_id:
                    metadata["operation_id"] = op_id
        except Exception:
            pass

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

    async def create_evaluation_sample(
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
            return await self._create_multi_turn_sample(parsed_trace)
        else:
            return self._create_single_turn_sample(parsed_trace)

    def _prepare_tool_contexts(self, parsed_trace: ParsedTrace) -> List[str]:
        """Prepare tool outputs as contexts for evaluation metrics.

        Args:
            parsed_trace: Parsed trace containing tool calls

        Returns:
            List of formatted context strings from tool outputs
        """
        contexts = []

        # Extract tool outputs with clear formatting
        for tool in parsed_trace.tool_calls:
            if tool.output and str(tool.output).strip() not in ["", "None"]:
                # Format tool context for better evaluation
                tool_context = self._format_tool_context(tool)
                if tool_context:
                    contexts.append(tool_context)

        # Extract memory-stored findings
        memory_findings = self._extract_memory_findings(parsed_trace)
        contexts.extend(memory_findings)

        # Include significant system messages
        for msg in parsed_trace.messages:
            if msg.role == "system" and "finding" in msg.content.lower():
                contexts.append(f"[System] {msg.content[:300]}")

        return contexts

    def _format_tool_context(self, tool: ParsedToolCall) -> Optional[str]:
        """Format a tool call output as an evaluation context.

        Args:
            tool: ParsedToolCall with output to format

        Returns:
            Formatted context string or None if not significant
        """
        output_str = str(tool.output).strip()

        # Special formatting for different tool types
        if tool.name == "shell":
            # Shell commands often have important output
            return f"[Shell Command Output] {output_str[:600]}"
        elif tool.name == "mem0_memory":
            # Memory operations contain findings
            if "store" in str(tool.input_data):
                return f"[Memory Store] {tool.input_data.get('content', '')[:400]}"
            else:
                return f"[Memory Operation] {output_str[:400]}"
        elif tool.name == "http_request":
            # HTTP responses for vulnerability testing
            return f"[HTTP Response] {output_str[:500]}"
        elif tool.name == "swarm":
            # Swarm agent results
            return f"[Swarm Agent] {output_str[:500]}"
        else:
            # Generic tool output
            return f"[{tool.name}] {output_str[:400]}"

    def _extract_memory_findings(self, parsed_trace: ParsedTrace) -> List[str]:
        """Extract significant security findings from memory operations.

        Args:
            parsed_trace: Parsed trace containing tool calls

        Returns:
            List of formatted finding contexts
        """
        findings = []

        # Determine current operation id if available for strict filtering
        current_op_id = None
        try:
            if isinstance(parsed_trace.metadata, dict):
                current_op_id = parsed_trace.metadata.get(
                    "operation_id"
                ) or parsed_trace.metadata.get("session_id")
        except Exception:
            current_op_id = None

        for tool in parsed_trace.tool_calls:
            if tool.name == "mem0_memory" and isinstance(tool.input_data, dict):
                action = tool.input_data.get("action", "")
                content = tool.input_data.get("content", "")
                meta = (
                    tool.input_data.get("metadata", {})
                    if isinstance(tool.input_data.get("metadata", {}), dict)
                    else {}
                )

                # When possible, include only store operations that belong to the current operation
                same_operation = True
                try:
                    op_id = meta.get("operation_id")
                    if op_id and current_op_id:
                        same_operation = op_id == current_op_id
                except Exception:
                    pass

                if action == "store" and content and same_operation:
                    # Emit concise context for current-session findings only
                    sev = meta.get("severity", "unknown")
                    cat = meta.get("category", "unknown")
                    findings.append(
                        f"[Security Finding - {sev}/{cat}] {str(content)[:500]}"
                    )

                elif action == "retrieve" and tool.output and same_operation:
                    # Include retrieved findings from this operation only
                    output_str = str(tool.output)
                    if output_str:
                        findings.append(f"[Retrieved Finding] {output_str[:400]}")

        return findings

    def count_current_evidence_findings(self, parsed_trace: ParsedTrace) -> int:
        """Count evidence findings restricted to the current operation id.

        This relies only on structured metadata equality checks, not patterns.
        """
        try:
            current_op_id = None
            if isinstance(parsed_trace.metadata, dict):
                current_op_id = parsed_trace.metadata.get(
                    "operation_id"
                ) or parsed_trace.metadata.get("session_id")
            if not current_op_id:
                return 0
            findings = 0
            for tool in parsed_trace.tool_calls:
                if tool.name == "mem0_memory" and isinstance(tool.input_data, dict):
                    meta = (
                        tool.input_data.get("metadata", {})
                        if isinstance(tool.input_data.get("metadata", {}), dict)
                        else {}
                    )
                    action = tool.input_data.get("action", "")
                    if (
                        meta.get("operation_id") == current_op_id
                        and action == "store"
                        and tool.input_data.get("content")
                    ):
                        findings += 1
            return findings
        except Exception:
            return 0

    def _create_single_turn_sample(self, parsed_trace: ParsedTrace) -> SingleTurnSample:
        """Create a SingleTurnSample for simple evaluations."""
        # Get user input (objective or first user message)
        user_input = parsed_trace.objective
        if not user_input and parsed_trace.messages:
            user_msgs = [
                msg.content for msg in parsed_trace.messages if msg.role == "user"
            ]
            user_input = user_msgs[0] if user_msgs else ""

        # Get agent response (final output or concatenated assistant messages)
        if parsed_trace.final_output:
            response = parsed_trace.final_output
        else:
            assistant_messages = [
                msg.content for msg in parsed_trace.messages if msg.role == "assistant"
            ]
            if not assistant_messages:
                # Use tool outputs as response if no assistant messages
                tool_outputs = parsed_trace.get_tool_outputs(limit=5)
                response = "\n".join(tool_outputs) if tool_outputs else ""
            else:
                response = "\n\n".join(assistant_messages[-3:])

        # Prepare comprehensive contexts from tools and findings
        contexts = self._prepare_tool_contexts(parsed_trace)

        logger.debug(
            "Created SingleTurnSample: input_len=%d, response_len=%d, contexts=%d",
            len(user_input),
            len(response),
            len(contexts),
        )

        return SingleTurnSample(
            user_input=user_input, response=response, retrieved_contexts=contexts
        )

    async def _generate_reference_topics_from_trace(
        self, parsed_trace: ParsedTrace
    ) -> List[str]:
        """Generate reference topics using LLM based on trace content.

        Uses the evaluation LLM to analyze the objective and tools used
        to generate appropriate reference topics for evaluation.

        Args:
            parsed_trace: Parsed trace containing objective and tool usage

        Returns:
            List of reference topics for TopicAdherence evaluation
        """
        if not self.llm:
            logger.warning(
                "No LLM provided for topic generation, using objective as topic"
            )
            return (
                [parsed_trace.objective]
                if parsed_trace.objective
                else ["cybersecurity assessment"]
            )

        # Prepare context for LLM to generate topics
        tools_used = list(set(t.name for t in parsed_trace.tool_calls))
        tool_summary = (
            f"Tools used: {', '.join(tools_used[:10])}"
            if tools_used
            else "No tools used"
        )

        # Include sample of findings if available
        findings_sample = []
        for tool in parsed_trace.tool_calls[:5]:
            if tool.name == "mem0_memory" and "store" in str(tool.input_data):
                if isinstance(tool.input_data, dict):
                    content = tool.input_data.get("content", "")
                    if content:
                        findings_sample.append(content[:200])

        findings_context = (
            "\n".join(findings_sample[:3])
            if findings_sample
            else "No findings documented yet"
        )

        f"""Analyze this cybersecurity operation and generate relevant reference topics.

Operation Context:
- Objective: {parsed_trace.objective}
- {tool_summary}
- Total operations performed: {len(parsed_trace.tool_calls)}
- Sample findings: {findings_context}

Generate 5-8 specific technical topics that this security assessment should cover based on the objective and operations performed. 
Topics should be specific to the security domain and techniques being used.

Return a JSON list of topic strings that represent the key areas this assessment should address."""

        try:
            from pydantic import BaseModel, Field

            # Define proper input and output models
            class TopicInput(BaseModel):
                """Input model for topic generation"""

                objective: str = Field(default="", description="Assessment objective")
                tools_summary: str = Field(
                    default="", description="Summary of tools used"
                )
                findings_context: str = Field(default="", description="Sample findings")

            class TopicsOutput(BaseModel):
                """Output model for generated topics"""

                topics: List[str] = Field(
                    description="List of technical reference topics for the security assessment"
                )

            # Generate topics using LLM with structured output
            if hasattr(self.llm, "generate"):
                from ragas.prompt import PydanticPrompt

                # Create prompt class with proper input/output models
                class TopicGenerationPrompt(PydanticPrompt[TopicInput, TopicsOutput]):
                    instruction = """Analyze this cybersecurity operation and generate relevant reference topics.

Operation Context:
- Objective: {{objective}}
- {{tools_summary}}
- Sample findings: {{findings_context}}

Generate 5-8 specific technical topics that this security assessment should cover based on the objective and operations performed. 
Topics should be specific to the security domain and techniques being used.

Return a JSON list of topic strings that represent the key areas this assessment should address."""
                    input_model = TopicInput
                    output_model = TopicsOutput

                # Create input data
                input_data = TopicInput(
                    objective=parsed_trace.objective or "security assessment",
                    tools_summary=tool_summary,
                    findings_context=findings_context,
                )

                # Generate topics
                topic_prompt = TopicGenerationPrompt()
                response = await topic_prompt.generate(
                    data=input_data, llm=self.llm, callbacks=None
                )

                if response and hasattr(response, "topics") and response.topics:
                    logger.debug(
                        f"LLM generated {len(response.topics)} topics: {response.topics}"
                    )
                    return response.topics
            else:
                # If generate method not available, use objective
                logger.warning(
                    "LLM does not support structured generation, using objective"
                )
                return (
                    [parsed_trace.objective]
                    if parsed_trace.objective
                    else ["cybersecurity assessment"]
                )

        except Exception as e:
            logger.error(f"Failed to generate topics with LLM: {e}")
            # Use objective as topic if LLM fails
            return (
                [parsed_trace.objective]
                if parsed_trace.objective
                else ["cybersecurity assessment"]
            )

    async def _create_multi_turn_sample(
        self, parsed_trace: ParsedTrace
    ) -> MultiTurnSample:
        """Create a MultiTurnSample for complex conversation evaluations."""
        # Convert messages to conversation format
        conversation = []

        # Ensure we have the objective as context
        if parsed_trace.objective:
            conversation.append(
                {"role": "user", "content": f"Objective: {parsed_trace.objective}"}
            )

        # Add all messages
        for msg in parsed_trace.messages:
            # Skip duplicate objective messages
            if msg.metadata.get("source") == "objective" and len(conversation) > 0:
                continue
            conversation.append({"role": msg.role, "content": msg.content})

        # Interleave tool outputs chronologically if possible
        tool_messages = []
        for tool in parsed_trace.tool_calls:
            if tool.output:
                output_str = str(tool.output).strip()
                if output_str and output_str != "None":
                    # Include more context for evaluation
                    content = f"Tool [{tool.name}]: {output_str[:400]}"
                    tool_messages.append({"role": "system", "content": content})

        # Add tool messages to conversation
        conversation.extend(tool_messages[:10])  # Limit to prevent overwhelming

        # Ensure we have substantive content
        if len(conversation) < 3:
            # Add summary of operations if conversation is too short
            if parsed_trace.tool_calls:
                tools_used = list(set(t.name for t in parsed_trace.tool_calls))
                conversation.append(
                    {
                        "role": "assistant",
                        "content": f"Executed {len(parsed_trace.tool_calls)} operations using {len(tools_used)} distinct tools",
                    }
                )

        logger.debug(
            "Created MultiTurnSample: %d messages (%d tool outputs included)",
            len(conversation),
            len(tool_messages),
        )

        # Generate reference topics based on objective and tool usage
        reference_topics = await self._generate_reference_topics_from_trace(
            parsed_trace
        )

        return MultiTurnSample(
            user_input=conversation,
            reference_topics=reference_topics,
        )
