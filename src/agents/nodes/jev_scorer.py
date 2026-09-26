import json
import logging
import os
import re
import time
import urllib.request
import urllib.error
from typing import Any, Dict

from src.agents.config import AgentConfig
from src.agents.state import FPLAgentState

logger = logging.getLogger(__name__)

JEV_SYSTEM_PROMPT = """You are TypeSafe Jev, an ultra-fast non-autoregressive FPL decision engine.
Analyze the provided specialist analytical findings and output a strict JSON object with your rapid tactical decision.

Respond ONLY with valid JSON in this exact structure:
{
  "verdict": "<short decisive action recommendation, max 10 words>",
  "hit_risk": "Low" | "Medium" | "High" | "None",
  "urgency_score": "<e.g., 85% or High / Moderate / Low>",
  "confidence_pct": <float between 50.0 and 99.0>,
  "primary_action": "TRANSFER" | "HOLD" | "CAPTAIN" | "CHIP" | "LINEUP",
  "key_metric": "<most critical statistical justification, max 12 words>"
}
"""


def _clean_json_text(text: str) -> str:
    """Extracts and sanitizes clean JSON substring."""
    text = text.strip()
    # 1. Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    # 2. Extract outermost JSON object if surrounded by preamble/postamble
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        text = brace_match.group(0).strip()
    # 3. Clean trailing commas before closing braces/brackets
    text = re.sub(r",\s*([\}\]])", r"\1", text)
    return text


def _parse_jev_json(raw_text: str) -> Dict[str, Any]:
    """Parses JSON safely with fallback sanitization."""
    cleaned = _clean_json_text(raw_text)
    try:
        return json.loads(cleaned)
    except Exception:
        # Fallback: remove control characters or try line-by-line repair
        sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned)
        return json.loads(sanitized)


def jev_scorer_node(state: FPLAgentState) -> Dict[str, Any]:
    """
    Executes Jev Decision scoring via direct OpenRouter REST API.
    Returns:
        jev_status: 'online' | 'unavailable'
        jev_result: Dict containing structured decision parameters or None
    """
    api_key = AgentConfig.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.info("OPENROUTER_API_KEY not configured. Jev decision engine marked as unavailable.")
        return {
            "jev_status": "unavailable",
            "jev_result": None,
            "next_node": "synthesis"
        }

    # Aggregate concise specialist context
    context_chunks = []
    if state.get("transfer_findings"):
        context_chunks.append(f"Transfer: {state['transfer_findings']}")
    if state.get("scout_findings"):
        context_chunks.append(f"Scout: {state['scout_findings']}")
    if state.get("horizon_findings"):
        context_chunks.append(f"Horizon: {state['horizon_findings']}")
    if state.get("chip_findings"):
        context_chunks.append(f"Chip: {state['chip_findings']}")
    if state.get("rival_findings"):
        context_chunks.append(f"Rival: {state['rival_findings']}")

    aggregated_context = "\n".join(context_chunks) if context_chunks else "No specific data loaded."
    user_query = ""
    messages = state.get("messages", [])
    if messages:
        last = messages[-1]
        user_query = last.content if hasattr(last, "content") else str(last)

    prompt = f"User Query: {user_query}\n\nSpecialist Findings:\n{aggregated_context}"
    model_name = AgentConfig.JEV_MODEL or os.getenv("JEV_MODEL", "typesafe/jev")

    start_time = time.perf_counter()
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://fpl-analyzer.local",
            "X-Title": "FPL Analyzer Jev Engine"
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": JEV_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 300
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            content = res_data["choices"][0]["message"]["content"]

        latency_ms = (time.perf_counter() - start_time) * 1000
        parsed = _parse_jev_json(content)
        parsed["latency_ms"] = round(latency_ms, 1)

        logger.info(f"✅ Jev scored decision in {latency_ms:.1f}ms: {parsed.get('verdict')}")
        return {
            "jev_status": "online",
            "jev_result": parsed,
            "next_node": "synthesis"
        }

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"⚠️ Jev OpenRouter HTTP {e.code} Error: {err_body}")
        logger.warning(f"⚠️ Jev Decision Engine HTTP error {e.code}: {err_body}. Marking as unavailable.")
        return {
            "jev_status": "unavailable",
            "jev_result": None,
            "next_node": "synthesis"
        }
    except Exception as e:
        print(f"⚠️ Jev Decision Engine unavailable ({e})")
        logger.warning(f"⚠️ Jev Decision Engine unavailable ({e}). Marking as unavailable.")
        return {
            "jev_status": "unavailable",
            "jev_result": None,
            "next_node": "synthesis"
        }
