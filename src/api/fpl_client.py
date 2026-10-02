"""
Comprehensive Official FPL API Client with integrated TTL caching.
Provides access to all core endpoints: static data, player stats (xG/xA/xGI),
fixtures, live gameweek stats, manager squad/history loading, multi-GW horizon projections,
combinatorial transfers, and chip strategy planning.
"""
from typing import Any, Dict, List, Optional
import pandas as pd

from src.api.base_client import BaseClient
from src.cache.cache_manager import CacheManager, get_cache
from src.config import FPLConfig
from src.models.manager import ManagerTeamListing, ManagerTeamPlayer, EntryHistory


class FPLClient:
    """Client for the Official Fantasy Premier League API with caching."""

    def __init__(self, client: Optional[BaseClient] = None, cache: Optional[CacheManager] = None):
        self.client = client or BaseClient(
            user_agent=FPLConfig.USER_AGENT, 
            timeout=FPLConfig.DEFAULT_TIMEOUT_SECONDS
        )
        self.cache = cache if cache is not None else get_cache()

    # -------------------------------------------------------------------------
    # 1. Core / Bootstrap Data (Players, Teams, Gameweeks, Positions)
    # -------------------------------------------------------------------------
    def get_bootstrap_static(self, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch the primary bootstrap static data containing:
        - 'elements': List of all 600+ players with full stats (xG, xA, price, form, etc.)
        - 'teams': List of 20 Premier League clubs
        - 'events': List of 38 Gameweeks with deadlines & status
        - 'element_types': Positional categories (GKP=1, DEF=2, MID=3, FWD=4)
        """
        if use_cache and not force_refresh:
            cached = self.cache.get("bootstrap_static")
            if cached:
                return cached

        data = self.client.get(FPLConfig.BOOTSTRAP_STATIC_URL)
        if use_cache and data:
            self.cache.set("bootstrap_static", data)
        return data

    def get_players_df(self, use_cache: bool = True, force_refresh: bool = False) -> pd.DataFrame:
        """
        Helper method returning a Pandas DataFrame of all players with
        convenient column conversions (now_cost in millions, numeric xG/xA/xGI).
        """
        data = self.get_bootstrap_static(use_cache=use_cache, force_refresh=force_refresh)
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
    def get_element_summary(self, player_id: int, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch detailed statistics for a specific player:
        - 'history': Match-by-match breakdown for the current season (xG, xA, minutes, points, opponent)
        - 'fixtures': Upcoming matches with FDR (Fixture Difficulty Rating)
        - 'history_past': Season totals for previous campaigns
        """
        if use_cache and not force_refresh:
            cached = self.cache.get("element_summary", identifier=player_id)
            if cached:
                return cached

        url = FPLConfig.ELEMENT_SUMMARY_URL.format(player_id=player_id)
        data = self.client.get(url)
        if use_cache and data:
            self.cache.set("element_summary", data, identifier=player_id)
        return data

    # -------------------------------------------------------------------------
    # 3. Fixtures
    # -------------------------------------------------------------------------
    def get_fixtures(self, event_id: Optional[int] = None, use_cache: bool = True, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch Premier League fixtures.
        :param event_id: Optional Gameweek number (1-38). If omitted, returns all 380 fixtures.
        """
        params = {"event": event_id} if event_id is not None else None
        cache_id = event_id if event_id is not None else "all"

        if use_cache and not force_refresh:
            cached = self.cache.get("fixtures", identifier=cache_id, params=params)
            if cached:
                return cached

        data = self.client.get(FPLConfig.FIXTURES_URL, params=params)
        if use_cache and data:
            self.cache.set("fixtures", data, identifier=cache_id, params=params)
        return data

    # -------------------------------------------------------------------------
    # 4. Live Gameweek Matchday Data
    # -------------------------------------------------------------------------
    def get_event_live(self, event_id: int, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch real-time live match statistics for a specific Gameweek.
        Returns live player points, goals, assists, saves, bonus points, BPS, and live xG.
        """
        if use_cache and not force_refresh:
            cached = self.cache.get("event_live", identifier=event_id)
            if cached:
                return cached

        url = FPLConfig.EVENT_LIVE_URL.format(event_id=event_id)
        data = self.client.get(url)
        if use_cache and data:
            self.cache.set("event_live", data, identifier=event_id)
        return data

    # -------------------------------------------------------------------------
    # 5. Manager & Team Loading
    # -------------------------------------------------------------------------
    def get_manager(self, manager_id: int, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch high-level manager profile:
        - Manager Name & Team Name
        - Overall points & overall rank
        - Current Gameweek rank
        - Region / country
        - Active leagues
        """
        if use_cache and not force_refresh:
            cached = self.cache.get("manager_entry", identifier=manager_id)
            if cached:
                return cached

        url = FPLConfig.MANAGER_ENTRY_URL.format(manager_id=manager_id)
        data = self.client.get(url)
        if use_cache and data:
            self.cache.set("manager_entry", data, identifier=manager_id)
        return data

    def get_manager_picks(self, manager_id: int, event_id: int, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch manager's exact squad selection for a given Gameweek:
        - 'picks': 15 players (1-11 starting XI, 12-15 bench) with 'is_captain', 'multiplier'
        - 'active_chip': Active chip for this GW ('wildcard', 'freehit', 'bboost', '3xc', or None)
        - 'entry_history': GW points, GW rank, squad value, bank, transfers made, transfer cost
        """
        if use_cache and not force_refresh:
            cached = self.cache.get("manager_picks", identifier=f"{manager_id}_gw{event_id}")
            if cached:
                return cached

        url = FPLConfig.MANAGER_PICKS_URL.format(manager_id=manager_id, event_id=event_id)
        data = self.client.get(url)
        if use_cache and data:
            self.cache.set("manager_picks", data, identifier=f"{manager_id}_gw{event_id}")
        return data

    def get_manager_history(self, manager_id: int, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch manager's performance history:
        - 'current': GW-by-GW breakdown across the season (rank, points, transfers, chips)
        - 'past': Final points and overall ranks from previous years
        - 'chips': List of chips used and which GW they were activated
        """
        if use_cache and not force_refresh:
            cached = self.cache.get("manager_history", identifier=manager_id)
            if cached:
                return cached

        url = FPLConfig.MANAGER_HISTORY_URL.format(manager_id=manager_id)
        data = self.client.get(url)
        if use_cache and data:
            self.cache.set("manager_history", data, identifier=manager_id)
        return data

    def get_manager_transfers(self, manager_id: int, use_cache: bool = True, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch complete log of all transfers made by the manager (element_in, element_out, event, time).
        """
        if use_cache and not force_refresh:
            cached = self.cache.get("manager_transfers", identifier=manager_id)
            if cached:
                return cached

        url = FPLConfig.MANAGER_TRANSFERS_URL.format(manager_id=manager_id)
        data = self.client.get(url)
        if use_cache and data:
            self.cache.set("manager_transfers", data, identifier=manager_id)
        return data

    def get_my_team(self, manager_id: int, cookie: Optional[str] = None, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch manager's private pre-deadline squad picks and active transfers for upcoming GW.
        Requires an authenticated FPL session cookie (`pl_profile`).
        """
        if use_cache and not force_refresh:
            cached = self.cache.get("my_team", identifier=manager_id)
            if cached:
                return cached

        url = FPLConfig.MY_TEAM_URL.format(manager_id=manager_id)
        fpl_cookie = cookie or FPLConfig.FPL_COOKIE
        headers = {}
        if fpl_cookie:
            c_str = fpl_cookie if ("=" in fpl_cookie) else f"pl_profile={fpl_cookie}"
            headers["Cookie"] = c_str
            
        data = self.client.get(url, headers=headers if headers else None)
        if use_cache and data:
            self.cache.set("my_team", data, identifier=manager_id)
        return data

    def get_manager_team(
        self, 
        manager_id: int, 
        event_id: Optional[int] = None, 
        return_model: bool = False,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Any:
        """
        Fetch the complete team listing for a manager in a given Gameweek, enriched with full player stats.
        Gracefully handles future/pre-deadline gameweeks by projecting from latest confirmed squad.
        """
        # 1. Fetch Manager Profile to resolve current event and metadata
        manager_data = self.get_manager(manager_id, use_cache=use_cache, force_refresh=force_refresh)
        current_event = manager_data.get("current_event") or 1
        target_gw = event_id or current_event
        manager_name = f"{manager_data.get('player_first_name', '')} {manager_data.get('player_last_name', '')}".strip()
        team_name = manager_data.get("name", "")

        # 2. Fetch Squad Picks (Strategy A: Cookie /my-team/, Strategy B: /picks/ for requested GW or fallback to current_event)
        picks = []
        entry_hist = {}
        active_chip = None

        from src.config import FPLConfig
        cookie_to_use = FPLConfig.FPL_COOKIE
        if cookie_to_use:
            try:
                my_team_data = self.get_my_team(manager_id, cookie=cookie_to_use, use_cache=use_cache)
                if isinstance(my_team_data, dict) and "picks" in my_team_data:
                    picks = my_team_data["picks"]
                    trans_info = my_team_data.get("transfers", {})
                    bank_raw = trans_info.get("bank", 0)
                    entry_hist = {"bank": bank_raw, "value": trans_info.get("value", 0)}
            except Exception:
                picks = []

        if not picks:
            squad_gw = target_gw if target_gw <= current_event else current_event
            try:
                picks_data = self.get_manager_picks(manager_id, squad_gw, use_cache=use_cache, force_refresh=force_refresh)
            except Exception:
                picks_data = self.get_manager_picks(manager_id, current_event, use_cache=use_cache, force_refresh=force_refresh)

            picks = picks_data.get("picks", [])
            active_chip = picks_data.get("active_chip")
            entry_hist = picks_data.get("entry_history", {})

        # 3. Fetch Bootstrap Static to resolve player, club, position names & stats
        bootstrap = self.get_bootstrap_static(use_cache=use_cache, force_refresh=force_refresh)
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
            pos_obj = positions_map.get(elem_type_id, {})
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

    def get_manager_team_df(self, manager_id: int, event_id: Optional[int] = None, use_cache: bool = True) -> pd.DataFrame:
        """
        Fetch manager squad as a clean, tabular Pandas DataFrame.
        """
        team_data = self.get_manager_team(manager_id, event_id, return_model=False, use_cache=use_cache)
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
    def get_classic_league(self, league_id: int, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch classic mini-league standings and manager points.
        """
        if use_cache and not force_refresh:
            cached = self.cache.get("classic_league", identifier=league_id)
            if cached:
                return cached

        url = FPLConfig.CLASSIC_LEAGUE_URL.format(league_id=league_id)
        data = self.client.get(url)
        if use_cache and data:
            self.cache.set("classic_league", data, identifier=league_id)
        return data

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
        use_cache: bool = True
    ):
        """
        Run complete predictive scoring and optimization analysis on a manager's squad.
        """
        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer = SquadAnalyzer(self)
        return analyzer.analyze_manager_squad(
            manager_id=manager_id, 
            gw=gw, 
            fpl_cookie=fpl_cookie, 
            transfers_in=transfers_in, 
            transfers_out=transfers_out,
            use_cache=use_cache
        )

    def get_squad_analysis_df(
        self, 
        manager_id: int, 
        gw: Optional[int] = None,
        fpl_cookie: Optional[str] = None,
        transfers_in: Optional[List[int]] = None,
        transfers_out: Optional[List[int]] = None,
        use_cache: bool = True
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
            transfers_out=transfers_out,
            use_cache=use_cache
        )

    def analyze_manager_horizon(
        self,
        manager_id: int,
        horizon_length: int = 5,
        start_gw: Optional[int] = None,
        fpl_cookie: Optional[str] = None,
        use_cache: bool = True
    ):
        """
        Run Multi-Gameweek Horizon analysis (e.g. Next 5 Gameweeks) for a manager.
        """
        from src.analysis.multi_gw_analyzer import MultiGWAnalyzer
        analyzer = MultiGWAnalyzer(self)
        return analyzer.analyze_manager_horizon(
            manager_id=manager_id,
            horizon_length=horizon_length,
            start_gw=start_gw,
            fpl_cookie=fpl_cookie,
            use_cache=use_cache
        )

    def optimize_transfers(
        self,
        manager_id: int,
        target_gw: Optional[int] = None,
        horizon_length: int = 4,
        free_transfers: int = 1,
        fpl_cookie: Optional[str] = None,
        use_cache: bool = True
    ):
        """
        Run Combinatorial Multi-Transfer optimization (1, 2, or 3 player swaps).
        """
        from src.analysis.transfer_optimizer import TransferOptimizer
        opt = TransferOptimizer(self)
        return opt.optimize_transfers(
            manager_id=manager_id,
            target_gw=target_gw,
            horizon_length=horizon_length,
            free_transfers=free_transfers,
            fpl_cookie=fpl_cookie,
            use_cache=use_cache
        )

    def evaluate_chips(
        self,
        manager_id: int,
        target_gw: Optional[int] = None,
        fpl_cookie: Optional[str] = None,
        use_cache: bool = True
    ):
        """
        Run Seasonal Chip Strategy and optimal execution calendar planning.
        """
        from src.analysis.chip_optimizer import ChipOptimizer
        opt = ChipOptimizer(self)
        return opt.evaluate_chips(
            manager_id=manager_id,
            target_gw=target_gw,
            fpl_cookie=fpl_cookie,
            use_cache=use_cache
        )

    def analyze_mini_league(
        self,
        league_id: int,
        target_manager_id: Optional[int] = None,
        gw: Optional[int] = None,
        use_cache: bool = True
    ):
        """
        Run Mini-League analysis, Effective Ownership (EO), and rival squad overlap comparisons.
        """
        from src.analysis.league_analyzer import LeagueAnalyzer
        analyzer = LeagueAnalyzer(self)
        return analyzer.analyze_mini_league(
            league_id=league_id,
            target_manager_id=target_manager_id,
            gw=gw,
            use_cache=use_cache
        )

    def close(self):
        """Close the underlying HTTP session."""
        self.client.close()
