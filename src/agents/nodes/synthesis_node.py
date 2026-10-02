"""
Synthesis Node: Generates the final cohesive, actionable FPL coaching and tactical recommendation.
"""
from typing import Any, Dict
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.config import get_llm
from src.agents.state import FPLAgentState

SYSTEM_PROMPT = """You are the **FPL Intelligence Head Coach & Tactical Advisor**.
Your mission is to provide concise, data-driven, and highly actionable Fantasy Premier League advice.
You are given verified underlying calculations and deterministic metrics from specialized analytical engines:
- Lineup & Expected Points (xP)
- Combinatorial Transfers & -4 Hit Break-Even analysis
- Understat Underlying Threat (npxG90, xA90, xGChain90, luck delta)
- Multi-Gameweek Horizon Projections & Fixture Swings
- Mini-League Effective Ownership (EO) & Rival Overlap

Format your answer with clear markdown headings, bullet points, and emoji tags.
Be direct, strategic, and give clear recommendations on:
1. 🏆 Recommended Lineup & Captain (C) / Vice-Captain (VC)
2. 🔄 Transfer Moves & Point Hit (-4) Justification
3. 🔍 Underlying Metrics & Differential Opportunities
4. 🗓️ Upcoming Schedule & Chip Strategy
Never invent stats or prices—rely solely on the provided specialist findings.
"""


def synthesis_node(state: FPLAgentState) -> Dict[str, Any]:
    """
    Synthesizes findings from all worker nodes and Jev into a final tactical briefing.
    """
    messages = state.get("messages", [])
    user_query = messages[-1].content if messages else "Gameweek advice"

    # 1. Format TypeSafe Jev Fast Decision Engine Block
    jev_status = state.get("jev_status")
    jev_result = state.get("jev_result")
    
    if jev_status == "online" and jev_result:
        jev_block = (
            f"## ⚡ TypeSafe Jev Fast Decision Engine\n"
            f"- **Verdict**: {jev_result.get('verdict', 'N/A')}\n"
            f"- **Hit Risk Assessment**: {jev_result.get('hit_risk', 'N/A')}\n"
            f"- **Transfer Urgency**: {jev_result.get('urgency_score', 'N/A')}\n"
            f"- **Recommendation Confidence**: {jev_result.get('confidence_pct', 'N/A')}%\n"
            f"- **Key Metric**: {jev_result.get('key_metric', 'N/A')}\n"
            f"- **Status**: 🟢 Online ({jev_result.get('latency_ms', 0):.0f}ms)"
        )
    else:
        jev_block = (
            f"## ⚡ TypeSafe Jev Fast Decision Engine\n"
            f"> ⚠️ **Status: Not Available** (API offline or OPENROUTER_API_KEY missing)\n"
            f"> *Fast non-autoregressive decision scoring could not be loaded.*"
        )

    # 2. Gather specialist findings
    findings_sections = []
    if state.get("scout_findings"):
        findings_sections.append(f"### 🔍 Scouting & Lineup Intelligence:\n{state['scout_findings']}")
    if state.get("transfer_findings"):
        findings_sections.append(f"### 🔄 Transfer & Hit Analysis:\n{state['transfer_findings']}")
    if state.get("horizon_findings"):
        findings_sections.append(f"### 🗓️ Multi-GW Horizon & Fixtures:\n{state['horizon_findings']}")
    if state.get("chip_findings"):
        findings_sections.append(f"### 🃏 Chip Strategy:\n{state['chip_findings']}")
    if state.get("rival_findings"):
        findings_sections.append(f"### 🏆 Mini-League & Rival Tactics:\n{state['rival_findings']}")

    aggregated_context = "\n\n".join(findings_sections) if findings_sections else "No specific data loaded."

    prompt_content = (
        f"User Question: {user_query}\n\n"
        f"Specialist Analytical Findings:\n{aggregated_context}\n\n"
    )
    if jev_result:
        prompt_content += f"Jev Decision Vector: {jev_result}\n\n"
    prompt_content += "Please synthesize this into a clear, decisive FPL tactical coaching recommendation for the user."

    # 3. LLM Synthesis
    try:
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt_content)
        ])
        llm_text = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        # Fallback to direct structured summary if LLM API key is not configured or offline
        llm_text = (
            f"### 📋 Specialist Analytical Report\n\n"
            f"{aggregated_context}\n\n"
            f"> [!NOTE]\n"
            f"> LLM Synthesis fallback active ({e}). Specialist algorithmic computations above are 100% accurate."
        )

    # 4. Final Combined Dual-Engine Output
    final_text = f"{jev_block}\n\n---\n\n## 🧠 Tactical Coach Advisory\n\n{llm_text}"
    ai_message = AIMessage(content=final_text)
    
    return {
        "final_response": final_text,
        "messages": [ai_message],
        "next_node": None
    }
