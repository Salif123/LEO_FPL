"""
LangChain tools for multi-gameweek horizon forecasting and league-wide fixture swings.
"""
from typing import Any, Dict, Optional
from langchain_core.tools import tool

from src.api.fpl_client import FPLClient


@tool
def get_multi_gameweek_horizon(
    manager_id: int,
    horizon_length: int = 5
) -> Dict[str, Any]:
    """
    Projects manager squad performance across a multi-gameweek forward planning window (e.g. Next 5 Gameweeks).
    Computes gameweek-by-gameweek optimal lineups, projected starting XI points, recommended captain
    for every future GW, and scans all 20 Premier League clubs for upcoming fixture swings.

    Args:
        manager_id: Official FPL manager ID.
        horizon_length: Planning window length in gameweeks (default 5, range 3-8).

    Returns:
        Forward projection breakdown per gameweek and top positive/negative league fixture swings.
    """
    client = FPLClient()
    report = client.analyze_manager_horizon(
        manager_id=manager_id,
        horizon_length=horizon_length
    )
    
    gw_breakdown = [
        {
            "gameweek": gw.gameweek,
            "projected_xp": round(gw.projected_xp, 2),
            "formation": gw.formation,
            "captain": {
                "name": gw.captain.player.web_name,
                "team": gw.captain.player.team_short_name,
                "captain_xp": round(gw.captain.expected_points, 2)
            }
        }
        for gw in report.gameweek_squads
    ]
    
    fixture_swings = [
        {
            "team": swing.team_name,
            "avg_fdr": round(swing.fdr_avg, 2),
            "sentiment": swing.sentiment,
            "key_assets": swing.key_assets
        }
        for swing in report.fixture_swings
    ]
    
    return {
        "manager_name": report.manager_name,
        "team_name": report.team_name,
        "horizon_length_gws": report.horizon_length,
        "total_horizon_xp": round(report.total_horizon_xp, 2),
        "avg_xp_per_gw": round(report.avg_xp_per_gw, 2),
        "gameweek_projections": gw_breakdown,
        "league_fixture_swings": fixture_swings[:6]
    }
