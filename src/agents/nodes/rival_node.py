"""
Rival & League Node: Tracks mini-league Effective Ownership (EO), rival squad overlap, and differential opportunities.
"""
from typing import Any, Dict
from src.agents.state import FPLAgentState
from src.agents.tools.league_tools import analyze_mini_league_and_rivals


def rival_node(state: FPLAgentState) -> Dict[str, Any]:
    """
    Analyzes mini-league Effective Ownership and head-to-head squad overlap against rivals.
    """
    league_id = state.get("league_id")
    manager_id = state.get("manager_id")

    if not league_id:
        return {
            "rival_findings": "Mini-league analysis skipped (No league_id provided).",
            "completed_tasks": (state.get("completed_tasks") or []) + ["rival"],
            "next_node": "supervisor"
        }

    league_data = analyze_mini_league_and_rivals.invoke({
        "league_id": league_id,
        "target_manager_id": manager_id
    })

    top_eo = league_data.get("top_effective_ownership", [])
    top_eo_str = ", ".join(f"{eo['player']} ({eo['team']}: {eo['effective_ownership_pct']}% EO, {eo['threat_sentiment']})" for eo in top_eo[:4])
    
    rivals = league_data.get("rival_comparisons", [])
    rival_lines = []
    if rivals:
        for r in rivals[:2]:
            rival_lines.append(f"  - Vs #{r['rival_rank']} {r['rival_name']}: Shared {r['shared_players']}, Captain: {r['captain']}, Differentials: {', '.join(r['your_differentials'])}")

    rival_text = (
        f"• League: {league_data.get('league_name')} ({league_data.get('total_managers')} Managers)\n"
        f"• Top EO Threats: {top_eo_str}\n"
        + ("• Rival Comparisons:\n" + "\n".join(rival_lines) if rival_lines else "")
    )

    completed = list(state.get("completed_tasks") or [])
    if "rival" not in completed:
        completed.append("rival")

    return {
        "rival_findings": rival_text,
        "completed_tasks": completed,
        "next_node": "supervisor"
    }
