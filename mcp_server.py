"""
FPL Intelligence Engine — Model Context Protocol (MCP) Server.
Exposes high-performance FPL transfer optimization, lineup solvers, chip planning,
and Understat expected metrics directly to Claude Desktop, Antigravity, and MCP clients.
"""
import sys
from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP
    except ImportError:
        from fastmcp import FastMCP

from src.agents.tools.squad_tools import (
    get_manager_squad_info,
    get_optimal_lineup_and_captain,
)
from src.agents.tools.transfer_tools import optimize_squad_transfers
from src.agents.tools.horizon_tools import get_multi_gameweek_horizon
from src.agents.tools.chip_tools import evaluate_chip_strategy
from src.agents.tools.league_tools import analyze_mini_league_and_rivals
from src.agents.tools.understat_tools import (
    get_understat_player_metrics,
    get_top_understat_underperformers,
)

# Initialize FastMCP Server
mcp = FastMCP("FPL Intelligence Engine")


# ============================================================================
# 1. Squad Inspection & Lineup Selection Tools
# ============================================================================

@mcp.tool()
def get_squad(manager_id: int, gameweek: Optional[int] = None) -> Dict[str, Any]:
    """
    Fetch complete live squad details for an FPL manager.

    Args:
        manager_id: The official FPL manager ID (e.g. 1209336).
        gameweek: Optional specific gameweek number. Defaults to current/active gameweek.

    Returns:
        Manager profile, bank balance, squad value, starting XI, and bench players with form & status.
    """
    try:
        return get_manager_squad_info.invoke({"manager_id": manager_id, "gameweek": gameweek})
    except Exception as exc:
        return {"error": str(exc), "manager_id": manager_id}


@mcp.tool()
def get_optimal_lineup(manager_id: int, gameweek: Optional[int] = None) -> Dict[str, Any]:
    """
    Computes the statistically optimal Starting XI, optimal formation (e.g. 3-4-3, 3-5-2),
    recommended Captain (C), Vice-Captain (VC), and ordered bench based on expected points (xP).

    Args:
        manager_id: The official FPL manager ID.
        gameweek: Optional target gameweek number.

    Returns:
        Lineup optimization report with projected points, optimal formation, captaincy, and bench order.
    """
    try:
        return get_optimal_lineup_and_captain.invoke({"manager_id": manager_id, "gameweek": gameweek})
    except Exception as exc:
        return {"error": str(exc), "manager_id": manager_id}


# ============================================================================
# 2. Transfer Optimization & Point-Hit Solver
# ============================================================================

@mcp.tool()
def optimize_transfers(
    manager_id: int,
    free_transfers: int = 1,
    horizon_length: int = 4,
    max_transfers: int = 2,
) -> Dict[str, Any]:
    """
    Evaluates combinatorial 1-player, 2-player, and 3-player transfer moves for an FPL squad.
    Calculates net xP gain, budget feasibility, and -4 / -8 point hit break-even gameweeks.

    Args:
        manager_id: Official FPL manager ID.
        free_transfers: Available free transfers (1 to 5, default 1).
        horizon_length: Forward planning window in gameweeks (default 4, range 1-8).
        max_transfers: Maximum transfer moves to evaluate simultaneously (1, 2, or 3).

    Returns:
        Ranked transfer combinations by net xP gain after hit deductions, with break-even horizons.
    """
    try:
        return optimize_squad_transfers.invoke({
            "manager_id": manager_id,
            "free_transfers": free_transfers,
            "horizon_length": horizon_length,
            "max_transfers": max_transfers,
        })
    except Exception as exc:
        return {"error": str(exc), "manager_id": manager_id}


# ============================================================================
# 3. Multi-Gameweek Horizon & Fixture Swings
# ============================================================================

@mcp.tool()
def get_horizon_projections(manager_id: int, horizon_length: int = 5) -> Dict[str, Any]:
    """
    Projects manager squad performance across a multi-gameweek forward planning window (3-8 GWs)
    and scans all 20 Premier League clubs for fixture difficulty swings (green runs vs red runs).

    Args:
        manager_id: Official FPL manager ID.
        horizon_length: Planning window length in gameweeks (default 5, range 3-8).

    Returns:
        Gameweek-by-gameweek projected points, recommended captain per GW, and top league fixture swings.
    """
    try:
        return get_multi_gameweek_horizon.invoke({
            "manager_id": manager_id,
            "horizon_length": horizon_length,
        })
    except Exception as exc:
        return {"error": str(exc), "manager_id": manager_id}


# ============================================================================
# 4. Chip Strategy & Seasonal Planning
# ============================================================================

@mcp.tool()
def evaluate_chips(manager_id: int) -> Dict[str, Any]:
    """
    Evaluates seasonal strategy for remaining FPL chips (Wildcard, Free Hit, Bench Boost,
    Triple Captain) and identifies optimal execution gameweek windows based on DGW/BGW schedules.

    Args:
        manager_id: Official FPL manager ID.

    Returns:
        Chip valuation report, recommended execution gameweeks, and anomaly calendars.
    """
    try:
        return evaluate_chip_strategy.invoke({"manager_id": manager_id})
    except Exception as exc:
        return {"error": str(exc), "manager_id": manager_id}


# ============================================================================
# 5. Mini-League & Rival Intelligence
# ============================================================================

@mcp.tool()
def analyze_mini_league(league_id: int, target_manager_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Analyzes an FPL Classic Mini-League for Effective Ownership (EO) threats,
    head-to-head squad overlap against rivals, and differential opportunities to climb rank.

    Args:
        league_id: The official FPL Classic Mini-League ID (e.g. 314 or 1209336).
        target_manager_id: Optional manager ID to run head-to-head differential comparisons.

    Returns:
        League standings, top Effective Ownership percentages, captaincy distribution, and rival differentials.
    """
    try:
        return analyze_mini_league_and_rivals.invoke({
            "league_id": league_id,
            "target_manager_id": target_manager_id,
        })
    except Exception as exc:
        return {"error": str(exc), "league_id": league_id}


# ============================================================================
# 6. Understat Expected Metrics & Luck Variance
# ============================================================================

@mcp.tool()
def get_understat_metrics(player_name: str, team_name: str = "") -> Dict[str, Any]:
    """
    Looks up deep underlying statistics from Understat for a Premier League footballer.
    Returns per-90 metrics (npxG90, xA90, xGChain90, xGBuildup90) and finishing luck variance (xG delta).

    Args:
        player_name: Player's common name or surname (e.g. "Haaland", "Saka", "Palmer", "Mbeumo").
        team_name: Optional team name to disambiguate players.

    Returns:
        Underlying metrics, total shots, key passes, per-90 threat, and luck sentiment.
    """
    try:
        return get_understat_player_metrics.invoke({
            "player_name": player_name,
            "team_name": team_name,
        })
    except Exception as exc:
        return {"error": str(exc), "player_name": player_name}


@mcp.tool()
def get_unlucky_underperformers(limit: int = 8) -> List[Dict[str, Any]]:
    """
    Scans all Premier League players on Understat with highest xG underperformance (xG > Goals).
    These players are statistically creating high quality chances but have suffered bad finishing luck,
    making them prime differential targets due for a scoring rebound.

    Args:
        limit: Number of top underperforming players to return (default 8).

    Returns:
        List of players with highest positive xG delta, goals, xG, and npxG90.
    """
    try:
        return get_top_understat_underperformers.invoke({"limit": limit})
    except Exception as exc:
        return [{"error": str(exc)}]


# ============================================================================
# 7. MCP Prompts (Reusable Workflow Templates for Claude)
# ============================================================================

@mcp.prompt()
def gameweek_prep_briefing(manager_id: int) -> str:
    """Complete pre-gameweek review prompt template."""
    return f"""Please perform a comprehensive FPL Gameweek tactical review for Manager ID {manager_id}:
1. Inspect the squad with `get_squad` and check player fitness, injuries, and bank balance.
2. Determine the optimal Starting XI, Captain (C), and Vice-Captain (VC) with `get_optimal_lineup`.
3. Check 1-2 transfer upgrade paths using `optimize_transfers` and analyze if taking a point hit (-4) is mathematically justified.
4. Verify underlying form for any potential transfer targets using `get_understat_metrics`.
5. Provide a structured tactical briefing with clear, actionable recommendations."""


@mcp.prompt()
def rival_differentials_briefing(league_id: int, manager_id: int) -> str:
    """Mini-league rival breakdown prompt template."""
    return f"""Analyze my mini-league (League ID: {league_id}, Manager ID: {manager_id}):
1. Call `analyze_mini_league` to check the top Effective Ownership (EO) players and captain choices across the league.
2. Identify high-risk players that could hurt my rank if they haul.
3. Highlight key differentials I own versus the top-ranked managers."""


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    # Stdio transport is used by Claude Desktop, Antigravity, and MCP clients
    mcp.run(transport="stdio")
