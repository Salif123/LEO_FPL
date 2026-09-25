"""
Transfer Node: Evaluates combinatorial 1, 2, and 3 player transfer moves and point hit break-evens.
"""
from typing import Any, Dict
from src.agents.state import FPLAgentState
from src.agents.tools.transfer_tools import optimize_squad_transfers


def transfer_node(state: FPLAgentState) -> Dict[str, Any]:
    """
    Simulates combinatorial transfers for the manager squad and evaluates net xP gains vs -4 hit costs.
    """
    manager_id = state.get("manager_id")
    if not manager_id:
        return {
            "transfer_findings": "Transfer analysis skipped (No manager_id provided).",
            "completed_tasks": (state.get("completed_tasks") or []) + ["transfer"],
            "next_node": "supervisor"
        }

    transfers_data = optimize_squad_transfers.invoke({
        "manager_id": manager_id,
        "free_transfers": 1,
        "horizon_length": 4,
        "max_transfers": 2
    })
    
    top_1 = transfers_data.get("best_1_transfer_moves", [])
    top_2 = transfers_data.get("best_2_transfer_moves", [])
    
    summary_lines = [
        f"Available Bank: £{transfers_data.get('current_bank_m', 0.0)}m | FTs: {transfers_data.get('available_free_transfers', 1)}"
    ]
    
    if top_1:
        summary_lines.append("Top 1-Transfer Moves:")
        for idx, move in enumerate(top_1[:2], start=1):
            summary_lines.append(
                f"  {idx}. OUT: {move['transfers_out']} -> IN: {move['transfers_in']} (+{move['net_horizon_gain']} net xP, Bank: £{move['remaining_bank_m']}m)"
            )
            
    if top_2:
        summary_lines.append("Top 2-Transfer Combo Swaps (Pair Transfers):")
        for idx, move in enumerate(top_2[:2], start=1):
            hit_pts = move['hits_taken'] * 4
            hit_txt = f" (Hit Cost: -{hit_pts} pts, Break-even: GW {move['break_even_gw']})" if move['hits_taken'] > 0 else " (Free)"
            summary_lines.append(
                f"  {idx}. OUT: {move['transfers_out']} -> IN: {move['transfers_in']} (+{move['net_horizon_gain']} net xP after hit{hit_txt}, Bank: £{move['remaining_bank_m']}m)"
            )

    transfer_text = "\n".join(summary_lines)
    
    completed = list(state.get("completed_tasks") or [])
    if "transfer" not in completed:
        completed.append("transfer")

    return {
        "transfer_findings": transfer_text,
        "completed_tasks": completed,
        "next_node": "supervisor"
    }
