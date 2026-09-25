"""
LangChain tools for Understat expected metrics (xG, xA, npxG90, xGChain90, and luck variance).
"""
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool

from src.analysis.understat_fusion import UnderstatFusion
from src.api.understat_client import UnderstatClient


@tool
def get_understat_player_metrics(player_name: str, team_name: str = "") -> Dict[str, Any]:
    """
    Looks up deep underlying performance statistics from Understat for a Premier League footballer.
    Returns per-90 metrics (npxG90, xA90, xGChain90, xGBuildup90) and finishing luck variance (xG delta).

    Args:
        player_name: The player's common name or surname (e.g. "Haaland", "Saka", "Palmer", "Mbeumo").
        team_name: Optional team name to disambiguate players.

    Returns:
        Underlying metrics, total shots, key passes, per-90 threat, and luck sentiment (unlucky / due a goal).
    """
    client = UnderstatClient()
    players = client.get_league_players()
    fusion = UnderstatFusion(understat_players=players)
    stats = fusion.match_player(web_name=player_name, team_name=team_name)
    
    if not stats:
        # Fallback: search FPL bootstrap to resolve full name & team for robust matching
        from src.api.fpl_client import FPLClient
        fpl = FPLClient()
        bootstrap = fpl.get_bootstrap_static()
        elements = bootstrap.get("elements", [])
        teams = {t["id"]: t["name"] for t in bootstrap.get("teams", [])}
        
        p_query = player_name.strip().lower()
        for elem in elements:
            web = elem.get("web_name", "").lower()
            first = elem.get("first_name", "").lower()
            second = elem.get("second_name", "").lower()
            full = f"{first} {second}"
            
            if p_query in [web, second, full] or p_query in web or p_query in full:
                t_name = teams.get(elem.get("team"), "")
                stats = fusion.match_player(
                    web_name=elem.get("web_name", ""),
                    first_name=elem.get("first_name", ""),
                    second_name=elem.get("second_name", ""),
                    team_name=team_name or t_name
                )
                if stats:
                    break
                    
    if not stats:
        return {
            "found": False,
            "message": f"No matching Understat player found for '{player_name}'."
        }
    
    sentiment = "Fairly Rated"
    if stats.xg_delta > 1.5:
        sentiment = "High xG Underperformance (Unlucky / Due a Goal)"
    elif stats.xg_delta < -1.5:
        sentiment = "High xG Overperformance (Clinical or Unsustainable Streak)"
    
    return {
        "found": True,
        "player_name": player_name,
        "goals": stats.goals,
        "xG": stats.xG,
        "npxG": stats.npxG,
        "assists": stats.assists,
        "xA": stats.xA,
        "xG_delta": stats.xg_delta,
        "finishing_sentiment": sentiment,
        "per_90_metrics": {
            "npxG90": stats.npxG90,
            "xA90": stats.xa90,
            "xGChain90": stats.xGChain90,
            "xGBuildup90": stats.xGBuildup90,
            "shots90": stats.shots90,
            "key_passes90": stats.key_passes90
        }
    }


@tool
def get_top_understat_underperformers(limit: int = 8) -> List[Dict[str, Any]]:
    """
    Scans all Premier League players on Understat to find footballers with the highest
    xG underperformance (xG > Goals). These players are statistically creating high quality
    chances but have been unlucky with finishing, making them prime differential targets ("due a goal").

    Args:
        limit: Number of players to return (default 8).

    Returns:
        List of players with highest positive xG delta, goals, xG, and npxG90.
    """
    client = UnderstatClient()
    players = client.get_league_players()
    if not players:
        return []
    
    enriched = []
    for p in players:
        goals = float(p.get("goals", 0))
        xg = float(p.get("xG", 0.0))
        time = float(p.get("time", 0))
        if time < 180:  # Minimum 2 full games played
            continue
        delta = round(xg - goals, 2)
        npxg = float(p.get("npxG", 0.0))
        npxg90 = round((npxg / (time / 90.0)), 2) if time > 0 else 0.0
        
        enriched.append({
            "player": p.get("player_name"),
            "team": p.get("team_title"),
            "goals": int(goals),
            "xG": round(xg, 2),
            "xg_delta_unlucky": delta,
            "npxG90": npxg90,
            "minutes": int(time)
        })
    
    # Sort descending by xg_delta (highest underperformance first)
    enriched.sort(key=lambda x: x["xg_delta_unlucky"], reverse=True)
    return enriched[:limit]
