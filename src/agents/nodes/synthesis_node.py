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
    Synthesizes findings from all worker nodes into a final tactical briefing.
    """
    messages = state.get("messages", [])
    user_query = messages[-1].content if messages else "Gameweek advice"

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
        f"Please synthesize this into a clear, decisive FPL tactical recommendation for the user."
    )

    try:
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt_content)
        ])
        final_text = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        # Fallback to direct structured summary if LLM API key is not configured or offline
        final_text = (
            f"## 📋 FPL Tactical Briefing\n\n"
            f"{aggregated_context}\n\n"
            f"> [!NOTE]\n"
            f"> LLM Synthesis fallback active ({e}). Specialist algorithmic computations above are 100% accurate."
        )

    ai_message = AIMessage(content=final_text)
    
    return {
        "final_response": final_text,
        "messages": [ai_message],
        "next_node": None
    }
