"""
LangChain tools for combinatorial FPL multi-transfer and point-hit (-4pt) optimization.
"""
from typing import Any, Dict, Optional
from langchain_core.tools import tool

from src.api.fpl_client import FPLClient


@tool
def optimize_squad_transfers(
    manager_id: int,
    free_transfers: int = 1,
    horizon_length: int = 4,
    max_transfers: int = 2
) -> Dict[str, Any]:
    """
    Evaluates all valid combinatorial 1-player, 2-player, and 3-player transfer swap combinations
    for a manager squad over an N-gameweek planning horizon.
    Calculates net expected points (xP) gained, cost feasibility against the bank,
    and point hit (-4 / -8 pts) break-even timelines.

    Args:
        manager_id: Official FPL manager ID.
        free_transfers: Available free transfers (1 to 5, default 1).
        horizon_length: Planning window in gameweeks (default 4).
        max_transfers: Maximum transfer moves to evaluate simultaneously (1, 2, or 3).

    Returns:
        A structured summary of top recommended transfer moves ranked by net xP gain after hits.
    """
    client = FPLClient()
    report = client.optimize_transfers(
        manager_id=manager_id,
        horizon_length=horizon_length,
        free_transfers=free_transfers
    )
    
    def format_combination(combo):
        out_str = ", ".join(f"{p.web_name} ({p.team_short_name})" for p in combo.players_out)
        in_str = ", ".join(f"{p.web_name} ({p.team_short_name})" for p in combo.players_in)
        return {
            "transfers_out": out_str,
            "transfers_in": in_str,
            "horizon_xp_gain": round(combo.horizon_xp_gain, 2),
            "hits_taken": combo.hits_taken,
            "net_horizon_gain": round(combo.net_horizon_gain, 2),
            "remaining_bank_m": round(combo.remaining_bank_m, 2),
            "break_even_gw": combo.break_even_gw,
            "rationale": combo.rationale
        }
    
    top_1 = [format_combination(c) for c in (report.single_transfers or [])[:3]]
    top_2 = [format_combination(c) for c in (report.double_transfers or [])[:3]]
    top_3 = [format_combination(c) for c in (report.triple_transfers or [])[:2]] if max_transfers >= 3 else []
    
    return {
        "manager_id": report.manager_id,
        "horizon_length_gws": report.horizon_length,
        "available_free_transfers": report.available_free_transfers,
        "current_bank_m": report.current_bank_m,
        "best_1_transfer_moves": top_1,
        "best_2_transfer_moves": top_2,
        "best_3_transfer_moves": top_3
    }
