"""
Lineup Node: Computes optimal starting XI, captaincy, vice-captaincy, and bench order.
"""
from typing import Any, Dict
from src.agents.state import FPLAgentState
from src.agents.tools.squad_tools import get_optimal_lineup_and_captain, get_manager_squad_info


def lineup_node(state: FPLAgentState) -> Dict[str, Any]:
    """
    Executes squad predictive scoring and lineup optimization for the target manager.
    """
    manager_id = state.get("manager_id")
    if not manager_id:
        return {
            "squad_summary": None,
            "completed_tasks": (state.get("completed_tasks") or []) + ["lineup"],
            "next_node": "supervisor"
        }

    # Fetch squad info and optimal lineup
    squad_info = get_manager_squad_info.invoke({"manager_id": manager_id})
    lineup_opt = get_optimal_lineup_and_captain.invoke({"manager_id": manager_id})
    
    starters_str = ", ".join(f"{p['name']} ({p['team']}, {p['expected_points']} xP)" for p in lineup_opt.get("starting_xi", []))
    bench_str = ", ".join(f"{p['name']} ({p['expected_points']} xP)" for p in lineup_opt.get("bench", []))
    cap = lineup_opt.get("recommended_captain", {})
    vc = lineup_opt.get("recommended_vice_captain", {})
    
    summary = (
        f"• Optimal Formation: {lineup_opt.get('optimal_formation')} (Total Projected: {lineup_opt.get('total_projected_xp')} xP)\n"
        f"• Captain: {cap.get('name')} ({cap.get('expected_points')} xP) | Vice-Captain: {vc.get('name')} ({vc.get('expected_points')} xP)\n"
        f"• Starters: {starters_str}\n"
        f"• Bench Order: {bench_str}\n"
        f"• Bank: £{squad_info.get('bank_m', 0.0)}m | Squad Value: £{squad_info.get('team_value_m', 0.0)}m"
    )

    completed = list(state.get("completed_tasks") or [])
    if "lineup" not in completed:
        completed.append("lineup")

    return {
        "squad_summary": squad_info,
        "bank_m": squad_info.get("bank_m"),
        "scout_findings": (state.get("scout_findings") or "") + f"\n[Lineup Analysis]\n{summary}",
        "completed_tasks": completed,
        "next_node": "supervisor"
    }
