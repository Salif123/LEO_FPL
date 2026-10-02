"""
LangChain tools for Mini-League intelligence, Effective Ownership (EO), and rival squad overlap analysis.
"""
from typing import Any, Dict, Optional
from langchain_core.tools import tool

from src.api.fpl_client import FPLClient


@tool
def analyze_mini_league_and_rivals(
    league_id: int,
    target_manager_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Analyzes an FPL Classic Mini-League to identify league-wide Effective Ownership (EO)
    threats, head-to-head squad overlap against rivals (including the #1 league leader),
    and differential opportunities for rank climbing.

    Args:
        league_id: The official FPL Classic Mini-League ID (e.g. 1209336).
        target_manager_id: Optional manager ID to run head-to-head differential comparisons against rivals.

    Returns:
        Mini-league standings, top Effective Ownership percentages, captain picks across the league,
        and squad differentials vs rivals.
    """
    client = FPLClient()
    report = client.analyze_mini_league(
        league_id=league_id,
        target_manager_id=target_manager_id
    )
    
    top_eo = [
        {
            "player": eo.web_name,
            "team": eo.team_short_name,
            "effective_ownership_pct": round(eo.effective_ownership_pct, 1),
            "threat_sentiment": eo.threat_sentiment,
            "starting_pct": round(eo.starting_pct, 1),
            "captain_pct": round(eo.captain_pct, 1)
        }
        for eo in (report.effective_ownership or [])[:8]
    ]
    
    rivals = [
        {
            "rival_rank": r.rival_rank,
            "rival_name": r.rival_name,
            "team_name": r.team_name,
            "captain": r.rival_captain,
            "shared_players": f"{r.shared_players_count}/15 ({r.overlap_percentage}%)",
            "your_differentials": r.user_differentials[:4],
            "rival_differentials": r.rival_differentials[:4]
        }
        for r in (report.rival_comparisons or [])[:5]
    ]
    
    return {
        "league_name": report.league_name,
        "total_managers": report.total_managers,
        "target_manager_name": report.target_manager_name,
        "target_manager_rank": report.target_manager_rank,
        "top_effective_ownership": top_eo,
        "rival_comparisons": rivals
    }
