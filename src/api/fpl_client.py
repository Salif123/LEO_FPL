"""
Comprehensive Official FPL API Client.
Provides access to all core endpoints: static data, player stats (xG/xA/xGI),
fixtures, live gameweek stats, and manager squad/history loading.
"""
from typing import Any, Dict, List, Optional
import pandas as pd

from src.api.base_client import BaseClient
from src.config import FPLConfig
from src.models.manager import ManagerTeamListing, ManagerTeamPlayer, EntryHistory


class FPLClient:
    """Client for the Official Fantasy Premier League API."""

    def __init__(self, client: Optional[BaseClient] = None):
        self.client = client or BaseClient(
            user_agent=FPLConfig.USER_AGENT, 
            timeout=FPLConfig.DEFAULT_TIMEOUT_SECONDS
        )

    # -------------------------------------------------------------------------
    # 1. Core / Bootstrap Data (Players, Teams, Gameweeks, Positions)
    # -------------------------------------------------------------------------
    def get_bootstrap_static(self) -> Dict[str, Any]:
        """
        Fetch the primary bootstrap static data containing:
        - 'elements': List of all 600+ players with full stats (xG, xA, price, form, etc.)
        - 'teams': List of 20 Premier League clubs
        - 'events': List of 38 Gameweeks with deadlines & status
        - 'element_types': Positional categories (GKP=1, DEF=2, MID=3, FWD=4)
        """
        return self.client.get(FPLConfig.BOOTSTRAP_STATIC_URL)

    def get_players_df(self) -> pd.DataFrame:
        """
        Helper method returning a Pandas DataFrame of all players with
        convenient column conversions (now_cost in millions, numeric xG/xA/xGI).
        """
        data = self.get_bootstrap_static()
        players = data.get("elements", [])
        teams = {t["id"]: t["name"] for t in data.get("teams", [])}
        positions = {et["id"]: et["singular_name_short"] for et in data.get("element_types", [])}

        df = pd.DataFrame(players)
        if df.empty:
            return df

        # Enrich with team and position names
        df["team_name"] = df["team"].map(teams)
        df["position"] = df["element_type"].map(positions)
        
        # Convert cost to standard million format (e.g., 100 -> 10.0m)
        df["cost_m"] = df["now_cost"] / 10.0
        
        # Convert numeric string fields to floats
        numeric_cols = [
            "expected_goals", "expected_assists", "expected_goal_involvements", 
            "expected_goals_conceded", "form", "ict_index", "selected_by_percent", 
            "points_per_game", "value_form", "value_season"
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df

    # -------------------------------------------------------------------------
    # 2. Individual Player Deep-Dive
    # -------------------------------------------------------------------------
    def get_element_summary(self, player_id: int) -> Dict[str, Any]:
        """
        Fetch detailed statistics for a specific player:
        - 'history': Match-by-match breakdown for the current season (xG, xA, minutes, points, opponent)
        - 'fixtures': Upcoming matches with FDR (Fixture Difficulty Rating)
        - 'history_past': Season totals for previous campaigns
        """
        url = FPLConfig.ELEMENT_SUMMARY_URL.format(player_id=player_id)
        return self.client.get(url)

    # -------------------------------------------------------------------------
    # 3. Fixtures
    # -------------------------------------------------------------------------
    def get_fixtures(self, event_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch Premier League fixtures.
        :param event_id: Optional Gameweek number (1-38). If omitted, returns all 380 fixtures.
        """
        params = {"event": event_id} if event_id is not None else None
        return self.client.get(FPLConfig.FIXTURES_URL, params=params)

    # -------------------------------------------------------------------------
    # 4. Live Gameweek Matchday Data
    # -------------------------------------------------------------------------
    def get_event_live(self, event_id: int) -> Dict[str, Any]:
        """
        Fetch real-time live match statistics for a specific Gameweek.
        Returns live player points, goals, assists, saves, bonus points, BPS, and live xG.
        """
        url = FPLConfig.EVENT_LIVE_URL.format(event_id=event_id)
        return self.client.get(url)

    # -------------------------------------------------------------------------
    # 5. Manager & Team Loading
    # -------------------------------------------------------------------------
    def get_manager(self, manager_id: int) -> Dict[str, Any]:
        """
        Fetch high-level manager profile:
        - Manager Name & Team Name
        - Overall points & overall rank
        - Current Gameweek rank
        - Region / country
        - Active leagues
        """
        url = FPLConfig.MANAGER_ENTRY_URL.format(manager_id=manager_id)
        return self.client.get(url)

    def get_manager_picks(self, manager_id: int, event_id: int) -> Dict[str, Any]:
        """
        Fetch manager's exact squad selection for a given Gameweek:
        - 'picks': 15 players (1-11 starting XI, 12-15 bench) with 'is_captain', 'multiplier'
        - 'active_chip': Active chip for this GW ('wildcard', 'freehit', 'bboost', '3xc', or None)
        - 'entry_history': GW points, GW rank, squad value, bank, transfers made, transfer cost
        """
        url = FPLConfig.MANAGER_PICKS_URL.format(manager_id=manager_id, event_id=event_id)
        return self.client.get(url)

    def get_manager_history(self, manager_id: int) -> Dict[str, Any]:
        """
        Fetch manager's performance history:
        - 'current': GW-by-GW breakdown across the season (rank, points, transfers, chips)
        - 'past': Final points and overall ranks from previous years
        - 'chips': List of chips used and which GW they were activated
        """
        url = FPLConfig.MANAGER_HISTORY_URL.format(manager_id=manager_id)
        return self.client.get(url)

    def get_manager_transfers(self, manager_id: int) -> List[Dict[str, Any]]:
        """
        Fetch complete log of all transfers made by the manager (element_in, element_out, event, time).
        """
        url = FPLConfig.MANAGER_TRANSFERS_URL.format(manager_id=manager_id)
        return self.client.get(url)

    def get_my_team(self, manager_id: int, cookie: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch manager's private pre-deadline squad picks and active transfers for upcoming GW.
        Requires an authenticated FPL session cookie (`pl_profile`).
        """
        url = FPLConfig.MY_TEAM_URL.format(manager_id=manager_id)
        fpl_cookie = cookie or FPLConfig.FPL_COOKIE
        headers = {}
        if fpl_cookie:
            c_str = fpl_cookie if ("=" in fpl_cookie) else f"pl_profile={fpl_cookie}"
            headers["Cookie"] = c_str
        return self.client.get(url, headers=headers if headers else None)

    def get_manager_team(
        self, 
        manager_id: int, 
        event_id: Optional[int] = None, 
        return_model: bool = False
    ) -> Any:
        """
        Fetch the complete team listing for a manager in a given Gameweek, enriched with full player stats.

        Merges manager squad picks with bootstrap static player, team, and position data.
        Returns detailed player data for both Starting XI and Bench:
        - Player web names, full names, clubs (e.g. Arsenal, Man City)
        - Positional types (GKP, DEF, MID, FWD) and squad order (1-15)
        - Captain (2x/3x) & Vice-Captain indicators
        - Pricing (£m), total points, form, expected goals (xG), expected assists (xA)
        - Squad value, bank balance, active chips, transfers cost

        :param manager_id: FPL Manager Entry ID (e.g. 1)
        :param event_id: Optional Gameweek number (1-38). If None, defaults to manager's current active Gameweek.
        :param return_model: If True, returns a Pydantic ManagerTeamListing instance; else returns a detailed Dict.
        """
        # 1. Fetch Manager Profile to resolve current event and metadata
        manager_data = self.get_manager(manager_id)
        target_gw = event_id or manager_data.get("current_event") or 1
        manager_name = f"{manager_data.get('player_first_name', '')} {manager_data.get('player_last_name', '')}".strip()
        team_name = manager_data.get("name", "")

        # 2. Fetch Squad Picks for target GW
        picks_data = self.get_manager_picks(manager_id, target_gw)
        picks = picks_data.get("picks", [])
        active_chip = picks_data.get("active_chip")
        entry_hist = picks_data.get("entry_history", {})

        # 3. Fetch Bootstrap Static to resolve player, club, position names & stats
        bootstrap = self.get_bootstrap_static()
        elements_map = {e["id"]: e for e in bootstrap.get("elements", [])}
        teams_map = {t["id"]: t for t in bootstrap.get("teams", [])}
        positions_map = {et["id"]: et for et in bootstrap.get("element_types", [])}

        # 4. Enrich each squad pick
        enriched_players: List[Dict[str, Any]] = []
        for pick in picks:
            elem_id = pick.get("element")
            pos_order = pick.get("position", 1)
            mult = pick.get("multiplier", 1)
            is_cap = bool(pick.get("is_captain", False))
            is_vc = bool(pick.get("is_vice_captain", False))

            elem = elements_map.get(elem_id, {})
            team_id = elem.get("team", 0)
            team_obj = teams_map.get(team_id, {})
            elem_type_id = elem.get("element_type", 0)
            raw_status = elem.get("status", "a")
            status_map = {
                "a": "Available",
                "d": "Doubtful",
                "i": "Injured",
                "s": "Suspended",
                "u": "Unavailable",
                "n": "Unavailable",
            }
            chance = elem.get("chance_of_playing_next_round")
            if raw_status == "d" and chance is not None:
                display_status = f"Doubtful ({chance}%)"
            else:
                display_status = status_map.get(raw_status, raw_status)

            player_dict: Dict[str, Any] = {
                "element": elem_id,
                "web_name": elem.get("web_name", "Unknown"),
                "first_name": elem.get("first_name", ""),
                "second_name": elem.get("second_name", ""),
                "team_id": team_id,
                "team_name": team_obj.get("name", "Unknown"),
                "team_short_name": team_obj.get("short_name", ""),
                "element_type": elem_type_id,
                "position": pos_obj.get("singular_name_short", "UNK"),
                "squad_position": pos_order,
                "is_starter": pos_order <= 11,
                "is_bench": pos_order > 11,
                "multiplier": mult,
                "is_captain": is_cap,
                "is_vice_captain": is_vc,
                "cost_m": round(float(elem.get("now_cost", 0)) / 10.0, 1),
                "total_points": int(elem.get("total_points", 0)),
                "form": float(elem.get("form", 0.0) or 0.0),
                "expected_goals": float(elem.get("expected_goals", 0.0) or 0.0),
                "expected_assists": float(elem.get("expected_assists", 0.0) or 0.0),
                "expected_goal_involvements": float(elem.get("expected_goal_involvements", 0.0) or 0.0),
                "status": display_status,
                "news": elem.get("news") or None,
                "chance_of_playing_next_round": chance,
            }
            enriched_players.append(player_dict)

        starting_xi = [p for p in enriched_players if p["is_starter"]]
        bench = [p for p in enriched_players if p["is_bench"]]

        bank_m = round(float(entry_hist.get("bank", 0)) / 10.0, 1) if entry_hist else 0.0
        val_raw = entry_hist.get("value") if entry_hist else None
        value_m = round(float(val_raw) / 10.0, 1) if val_raw is not None else round(sum(p["cost_m"] for p in enriched_players), 1)

        result_dict = {
            "manager_id": manager_id,
            "manager_name": manager_name,
            "team_name": team_name,
            "event_id": target_gw,
            "active_chip": active_chip,
            "entry_history": entry_hist if entry_hist else None,
            "team_value_m": value_m,
            "bank_m": bank_m,
            "starting_xi": starting_xi,
            "bench": bench,
            "players": enriched_players,
        }

        if return_model:
            return ManagerTeamListing(
                manager_id=manager_id,
                manager_name=manager_name,
                team_name=team_name,
                event_id=target_gw,
                active_chip=active_chip,
                entry_history=EntryHistory(**entry_hist) if entry_hist else None,
                team_value_m=value_m,
                bank_m=bank_m,
                starting_xi=[ManagerTeamPlayer(**p) for p in starting_xi],
                bench=[ManagerTeamPlayer(**p) for p in bench],
                players=[ManagerTeamPlayer(**p) for p in enriched_players],
            )

        return result_dict

    def get_manager_team_df(self, manager_id: int, event_id: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch manager squad as a clean, tabular Pandas DataFrame.
        Includes squad position, role (Starter / Bench), player name, club, position,
        cost, captain status, points, form, xG, and xA.
        """
        team_data = self.get_manager_team(manager_id, event_id, return_model=False)
        players = team_data.get("players", [])

        rows = []
        for p in players:
            role = "Starter" if p["is_starter"] else f"Bench (Sub {p['squad_position'] - 11})"
            captaincy = ""
            if p["is_captain"]:
                captaincy = f"Captain ({p['multiplier']}x)" if p["multiplier"] > 1 else "Captain"
            elif p["is_vice_captain"]:
                captaincy = "Vice-Captain"

            rows.append({
                "pos_no": p["squad_position"],
                "role": role,
                "player": p["web_name"],
                "team": p["team_short_name"] or p["team_name"],
                "pos": p["position"],
                "cost_m": f"£{p['cost_m']:.1f}m",
                "captaincy": captaincy,
                "total_pts": p["total_points"],
                "form": p["form"],
                "xG": p["expected_goals"],
                "xA": p["expected_assists"],
                "status": "Available" if p["status"] == "a" else (p["news"] or p["status"]),
            })

        df = pd.DataFrame(rows)
        return df


    # -------------------------------------------------------------------------
    # 6. Mini-Leagues
    # -------------------------------------------------------------------------
    def get_classic_league(self, league_id: int) -> Dict[str, Any]:
        """
        Fetch classic mini-league standings and manager points.
        """
        url = FPLConfig.CLASSIC_LEAGUE_URL.format(league_id=league_id)
        return self.client.get(url)

    # -------------------------------------------------------------------------
    # 7. Squad Analysis & Predictive Scoring
    # -------------------------------------------------------------------------
    def analyze_manager_squad(
        self, 
        manager_id: int, 
        gw: Optional[int] = None,
        fpl_cookie: Optional[str] = None,
        transfers_in: Optional[List[int]] = None,
        transfers_out: Optional[List[int]] = None,
    ):
        """
        Run complete predictive scoring and optimization analysis on a manager's squad.
        Returns a ManagerSquadAnalysisReport with starting XI optimization, captain recommendations,
        and fixture difficulty analysis.
        
        :param manager_id: FPL Manager Entry ID
        :param gw: Target Gameweek (defaults to upcoming gameweek)
        :param fpl_cookie: Optional FPL session cookie to fetch pre-deadline saved transfers from /my-team/
        :param transfers_in: Optional list of player IDs to simulate adding to the squad
        :param transfers_out: Optional list of player IDs to simulate removing from the squad
        """
        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer = SquadAnalyzer(self)
        return analyzer.analyze_manager_squad(
            manager_id=manager_id, 
            gw=gw, 
            fpl_cookie=fpl_cookie, 
            transfers_in=transfers_in, 
            transfers_out=transfers_out
        )

    def get_squad_analysis_df(
        self, 
        manager_id: int, 
        gw: Optional[int] = None,
        fpl_cookie: Optional[str] = None,
        transfers_in: Optional[List[int]] = None,
        transfers_out: Optional[List[int]] = None,
    ) -> pd.DataFrame:
        """
        Export manager squad analysis and score breakdown as a sorted Pandas DataFrame.
        """
        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer = SquadAnalyzer(self)
        return analyzer.get_squad_analysis_df(
            manager_id=manager_id, 
            gw=gw, 
            fpl_cookie=fpl_cookie, 
            transfers_in=transfers_in, 
            transfers_out=transfers_out
        )

    def close(self):
        """Close the underlying HTTP session."""
        self.client.close()

