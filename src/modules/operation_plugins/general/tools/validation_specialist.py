"""Validation specialist - Rigorous false positive prevention."""

import json
import logging

from strands import Agent, tool
from modules.config.manager import ConfigManager

logger = logging.getLogger(__name__)


VALIDATION_METHODOLOGY = """<validation_specialist>
<role>Evidence validator - Apply scientific method to security claims</role>

<mandate>
Prevent false positives via 7-gate validation checklist. Each gate must PASS for verified status.
</mandate>

<seven_gates>
<gate id="1" name="Baseline Artifact">
  - Requirement: Pre-exploit state captured in artifact
  - Test: Artifact file exists and readable
  - Failure: No baseline comparison possible
</gate>

<gate id="2" name="Exploit Artifact">
  - Requirement: Post-exploit state captured in artifact
  - Test: Artifact file exists and readable
  - Failure: No exploit evidence
</gate>

<gate id="3" name="Content Differential">
  - Requirement: Semantic content change (not just metadata)
  - Test: diff baseline vs exploit shows meaningful change
  - Failure: Status/size change only = Same layer, different variation
</gate>

<gate id="4" name="Causality">
  - Requirement: YOUR change caused THEIR response change
  - Test: Repeat exploit→same outcome | Omit exploit→different outcome
  - Failure: Non-reproducible or correlation without causation
</gate>

<gate id="5" name="Data Extraction">
  - Requirement: If claiming "extracted X", X must be IN response
  - Test: grep exploit_artifact for claimed data (e.g. session_token, admin hash)
  - Failure: Claimed data NOT in response (was in payload sent, not received)
</gate>

<gate id="6" name="Layer Discrimination">
  - Requirement: Backend reached, not just different defensive layer
  - Test: Response contains application content (not WAF/CDN/challenge page)
  - Failure: Same error type (both Cloudflare, both WAF) = Same layer
</gate>

<gate id="7" name="Authorization">
  - Requirement: Bypass claims need 2xx + protected data
  - Test: 40x = Authorization blocking (NOT bypassed) | 2xx + data = Bypass
  - Failure: "Got 403" ≠ "Bypassed auth" (403 = blocked)
</gate>
</seven_gates>

<decision_logic>
ALL gates PASS:
  - validation_status: "verified"
  - confidence: No penalty
  - severity_max: As claimed (CRITICAL/HIGH)

ANY gate FAILS:
  - validation_status: "hypothesis"
  - confidence: Deduct 15% per failed gate
  - severity_max: Cap at MEDIUM (too weak for HIGH/CRITICAL)

Layer confusion (defensive layer mistaken for backend):
  - severity_max: Cap at INFO
</decision_logic>

<output_format>
Return JSON only:
{
  "validation_status": "verified" | "hypothesis" | "error",
  "confidence": 0-100,
  "severity_max": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO",
  "failed_gates": [1, 2, 3, 4, 5, 6, 7],
  "evidence_summary": "Detailed findings from artifact inspection",
  "recommendation": "Specific next action"
}
</output_format>

<execution_protocol>
1. Use editor to read each artifact in artifact_paths
2. Apply gates systematically (don't skip any)
3. For extraction claims: grep artifact for specific data
4. For bypass claims: diff artifacts for semantic content change
5. Document which gates passed/failed with evidence
6. Return JSON result only
</execution_protocol>
</validation_specialist>"""


def _create_specialist_model():
    """Create model for specialist - reuse main LLM/provider when swarm override is unavailable."""
    import os
    from modules.config.models.factory import create_bedrock_model, create_ollama_model, create_litellm_model
    from modules.config.manager import ConfigManager

    provider = os.getenv("CYBER_AGENT_PROVIDER", "bedrock")
    config_manager = ConfigManager()
    swarm_model_id = config_manager.get_swarm_model_id()
    region = os.getenv("AWS_REGION", config_manager.getenv("AWS_REGION", "us-east-1"))

    def _build(model_id: str):
        if provider == "bedrock":
            return create_bedrock_model(model_id, region, provider)
        if provider == "ollama":
            return create_ollama_model(model_id, provider)
        if provider == "litellm":
            return create_litellm_model(model_id, region, provider)
        raise ValueError(f"Unknown provider: {provider}")

    try:
        return _build(swarm_model_id)
    except Exception as exc:  # fall back to main LLM if swarm override is misconfigured
        primary_model = config_manager.get_llm_config(provider).model_id
        logger.warning(
            "Specialist model '%s' unavailable for provider '%s' (%s). Falling back to main model '%s'.",
            swarm_model_id,
            provider,
            exc,
            primary_model,
        )
        return _build(primary_model)



@tool
def validation_specialist(
    finding_description: str,
    artifact_paths: list[str],
    claimed_severity: str = "HIGH"
) -> dict:
    """Validate HIGH/CRITICAL findings via rigorous 7-gate checklist."""
    try:
        from strands_tools import editor, shell

        validator = Agent(
            model=_create_specialist_model(),
            system_prompt=VALIDATION_METHODOLOGY,
            tools=[editor, shell],
            
        )

        task = f"""Validate security finding:

CLAIMED FINDING:
{finding_description}

CLAIMED SEVERITY: {claimed_severity}

ARTIFACTS:
{json.dumps(artifact_paths, indent=2)}

Execute 7-gate validation checklist. Return JSON only."""

        result = validator(task)
        result_text = str(result)

        # Parse JSON from response
        if "{" in result_text and "}" in result_text:
            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1
            json_str = result_text[json_start:json_end]
            return json.loads(json_str)

        # Fallback if no JSON found
        return {
            "validation_status": "hypothesis",
            "confidence": 40,
            "severity_max": "MEDIUM",
            "failed_gates": list(range(1, 8)),
            "evidence_summary": "Could not parse validation results",
            "recommendation": "Manually review artifacts"
        }

    except Exception as e:
        logger.error(f"Validation specialist error: {e}")
        return {
            "validation_status": "error",
            "confidence": 0,
            "severity_max": "INFO",
            "failed_gates": [],
            "evidence_summary": f"Validation error: {str(e)}",
            "recommendation": "Fix specialist configuration"
        }
