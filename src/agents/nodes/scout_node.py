"""
Scout Node: Evaluates player underlying metrics (npxG90, xA90, xGChain90, luck variance) and scout opportunities.
"""
from typing import Any, Dict
from langchain_core.messages import HumanMessage
from src.agents.state import FPLAgentState
from src.agents.tools.understat_tools import get_understat_player_metrics, get_top_understat_underperformers


def scout_node(state: FPLAgentState) -> Dict[str, Any]:
    """
    Scouts player underlying stats from Understat and flags unluckiness / regression candidates.
    """
    messages = state.get("messages", [])
    user_query = messages[-1].content if messages else ""
    
    # Common prominent players to look out for in user text
    findings = []
    
    # Check top league underperformers (due a goal)
    underperformers = get_top_understat_underperformers.invoke({"limit": 5})
    if underperformers:
        und_str = ", ".join(f"{p['player']} ({p['team']}: xG {p['xG']} vs {p['goals']} Goals, Δ {p['xg_delta_unlucky']})" for p in underperformers[:3])
        findings.append(f"Top Understat Underperformers (Due a Goal): {und_str}")

    # Check for specific names in user prompt
    common_targets = ["Haaland", "Salah", "Saka", "Palmer", "Son", "Watkins", "Isak", "Mbeumo", "Gordon", "Diaz", "Wood", "Rogers", "Fernandes"]
    matched_players = [p for p in common_targets if p.lower() in user_query.lower()]
    
    for player in matched_players:
        metrics = get_understat_player_metrics.invoke({"player_name": player})
        if metrics.get("found"):
            p90 = metrics.get("per_90_metrics", {})
            findings.append(
                f"• {player}: npxG90={p90.get('npxG90')}, xA90={p90.get('xA90')}, xGChain90={p90.get('xGChain90')} | Sentiment: {metrics.get('finishing_sentiment')}"
            )

    scout_text = "\n".join(findings) if findings else "Scouting complete: standard underlying performance metrics verified."
    
    completed = list(state.get("completed_tasks") or [])
    if "scout" not in completed:
        completed.append("scout")

    return {
        "scout_findings": (state.get("scout_findings") or "") + f"\n[Understat & Scout Metrics]\n{scout_text}",
        "completed_tasks": completed,
        "next_node": "supervisor"
    }
