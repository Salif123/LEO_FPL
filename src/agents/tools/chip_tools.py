"""
LangChain tools for seasonal FPL chip strategy planning (Wildcard, Free Hit, Bench Boost, Triple Captain).
"""
from typing import Any, Dict, Optional
from langchain_core.tools import tool

from src.api.fpl_client import FPLClient


@tool
def evaluate_chip_strategy(manager_id: int) -> Dict[str, Any]:
    """
    Evaluates seasonal strategy and optimal execution windows for remaining FPL chips:
    Wildcard (WC), Free Hit (FH), Bench Boost (BB), and Triple Captain (TC).
    Detects upcoming Double Gameweeks (DGW), Blank Gameweeks (BGW), and squad structural decay.

    Args:
        manager_id: Official FPL manager ID.

    Returns:
        Comprehensive chip valuation report, recommended execution gameweeks, and anomaly calendars.
    """
    client = FPLClient()
    report = client.evaluate_chips(manager_id=manager_id)
    
    recommendations = [
        {
            "chip": r.chip_name,
            "recommended_gw": r.recommended_gw,
            "projected_upside_xp": round(r.projected_upside_xp, 2),
            "confidence_score": r.confidence_score,
            "trigger_reason": r.trigger_reason,
            "alternative_gws": r.alternative_gws
        }
        for r in report.recommendations
    ]
    
    return {
        "manager_id": report.manager_id,
        "chips_remaining": report.chips_remaining,
        "chips_used": report.chips_used,
        "recommended_chip_roadmap": recommendations,
        "optimal_calendar_summary": report.optimal_calendar_summary
    }
