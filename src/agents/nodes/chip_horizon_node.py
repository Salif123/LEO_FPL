"""
Chip & Horizon Node: Projects multi-gameweek schedules, fixture swings, and seasonal chip strategies.
"""
from typing import Any, Dict
from src.agents.state import FPLAgentState
from src.agents.tools.horizon_tools import get_multi_gameweek_horizon
from src.agents.tools.chip_tools import evaluate_chip_strategy


def chip_horizon_node(state: FPLAgentState) -> Dict[str, Any]:
    """
    Evaluates multi-GW horizon trends, fixture swings, and seasonal chip valuations (WC, FH, BB, TC).
    """
    manager_id = state.get("manager_id")
    chip_text = ""
    horizon_text = ""

    if manager_id:
        # 1. Horizon & Fixture Swings
        horizon_data = get_multi_gameweek_horizon.invoke({
            "manager_id": manager_id,
            "horizon_length": 5
        })
        swings = horizon_data.get("league_fixture_swings", [])
        swings_str = ", ".join(f"{s['team']} ({s['sentiment']}, avg FDR {s['avg_fdr']})" for s in swings[:3])
        horizon_text = (
            f"• 5-GW Projected Total: {horizon_data.get('total_horizon_xp')} pts (Avg: {horizon_data.get('avg_xp_per_gw')} pts/GW)\n"
            f"• Top League Fixture Swings: {swings_str}"
        )

        # 2. Chip Strategy
        chip_data = evaluate_chip_strategy.invoke({"manager_id": manager_id})
        roadmap = chip_data.get("recommended_chip_roadmap", [])
        roadmap_str = ", ".join(f"{r['chip']} -> GW {r['recommended_gw']} (+{r['projected_upside_xp']} xP upside, {r['trigger_reason']})" for r in roadmap)
        chip_text = (
            f"• Remaining Chips: {', '.join(chip_data.get('chips_remaining', [])) or 'None'}\n"
            f"• Recommended Roadmap: {roadmap_str}"
        )
    else:
        horizon_text = "Horizon analysis: Provide a manager_id for personalized multi-GW projections."
        chip_text = "Chip analysis: Provide a manager_id to evaluate remaining chips."

    completed = list(state.get("completed_tasks") or [])
    for task in ["chip", "horizon"]:
        if task in (state.get("required_tasks") or []) and task not in completed:
            completed.append(task)

    return {
        "horizon_findings": horizon_text,
        "chip_findings": chip_text,
        "completed_tasks": completed,
        "next_node": "supervisor"
    }
