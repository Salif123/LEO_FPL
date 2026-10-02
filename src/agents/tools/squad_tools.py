"""
LangChain tools for FPL Manager Squad inspection, starting XI selection, and captaincy optimization.
"""
from typing import Any, Dict, Optional
from langchain_core.tools import tool

from src.api.fpl_client import FPLClient


@tool
def get_manager_squad_info(manager_id: int, gameweek: Optional[int] = None) -> Dict[str, Any]:
    """
    Fetch complete squad details for an FPL manager, including player names, positions,
    teams, current selling/purchase prices, bank balance, and active chip.

    Args:
        manager_id: The official FPL manager ID (e.g. 1209336).
        gameweek: Optional specific gameweek number. If omitted, uses the latest/active gameweek.

    Returns:
        A dictionary containing manager profile, bank, squad value, starting XI, and bench players.
    """
    client = FPLClient()
    team_data = client.get_manager_team(manager_id=manager_id, event_id=gameweek, return_model=False)
    
    starters_summary = [
        {
            "name": p["web_name"],
            "position": p["position"],
            "team": p["team_short_name"],
            "cost_m": p["cost_m"],
            "is_captain": p["is_captain"],
            "is_vice_captain": p["is_vice_captain"],
            "form": p["form"],
            "total_points": p["total_points"],
            "status": p["status"],
            "news": p.get("news", "")
        }
        for p in team_data.get("starting_xi", [])
    ]
    
    bench_summary = [
        {
            "name": p["web_name"],
            "position": p["position"],
            "team": p["team_short_name"],
            "cost_m": p["cost_m"],
            "sub_order": p["squad_position"] - 11,
            "status": p["status"],
            "news": p.get("news", "")
        }
        for p in team_data.get("bench", [])
    ]
    
    return {
        "manager_id": team_data["manager_id"],
        "manager_name": team_data["manager_name"],
        "team_name": team_data["team_name"],
        "gameweek": team_data["event_id"],
        "bank_m": team_data["bank_m"],
        "team_value_m": team_data["team_value_m"],
        "active_chip": team_data["active_chip"],
        "starting_xi": starters_summary,
        "bench": bench_summary
    }


@tool
def get_optimal_lineup_and_captain(manager_id: int, gameweek: Optional[int] = None) -> Dict[str, Any]:
    """
    Computes the statistically optimal Starting XI, optimal formation (e.g. 3-4-3, 3-5-2),
    recommended Captain (C), Vice-Captain (VC), and ordered bench for an FPL manager squad
    based on expected points (xP), fixture difficulty (FDR), form, and underlying threat.

    Args:
        manager_id: The official FPL manager ID.
        gameweek: Optional target gameweek number.

    Returns:
        Detailed lineup optimization report with projected points, optimal formation,
        and captaincy recommendations.
    """
    client = FPLClient()
    report = client.analyze_manager_squad(manager_id=manager_id, gw=gameweek)
    opt = report.optimization
    
    starting_xi = []
    for p in opt.recommended_starting_xi:
        fixture_str = "N/A"
        if p.fixtures:
            fix = p.fixtures[0]
            fixture_str = f"{fix.opponent_short_name} ({'H' if fix.is_home else 'A'}, FDR {fix.difficulty})"
        
        starting_xi.append({
            "name": p.web_name,
            "position": p.position,
            "team": p.team_short_name,
            "expected_points": round(p.score_breakdown.expected_points, 2),
            "composite_score": p.score_breakdown.composite_score,
            "opponent": fixture_str,
            "is_captain": (p.element == opt.recommended_captain.element),
            "is_vice_captain": (p.element == opt.recommended_vice_captain.element)
        })
    
    bench = []
    for idx, p in enumerate(opt.recommended_bench, start=1):
        bench.append({
            "name": p.web_name,
            "position": p.position,
            "team": p.team_short_name,
            "sub_order": idx,
            "expected_points": round(p.score_breakdown.expected_points, 2),
            "status": p.status
        })
    
    return {
        "manager_name": report.manager_name,
        "gameweek": report.target_gameweek,
        "optimal_formation": opt.formation,
        "total_projected_xp": round(opt.total_projected_xp, 2),
        "recommended_captain": {
            "name": opt.recommended_captain.web_name,
            "team": opt.recommended_captain.team_short_name,
            "expected_points": round(opt.recommended_captain.score_breakdown.expected_points, 2),
            "index_score": opt.recommended_captain.score_breakdown.composite_score
        },
        "recommended_vice_captain": {
            "name": opt.recommended_vice_captain.web_name,
            "team": opt.recommended_vice_captain.team_short_name,
            "expected_points": round(opt.recommended_vice_captain.score_breakdown.expected_points, 2)
        },
        "starting_xi": starting_xi,
        "bench": bench
    }
