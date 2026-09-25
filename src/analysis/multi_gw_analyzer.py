"""
Multi-Gameweek Horizon Engine for FPL Squad Projections and Fixture Run Analytics.
Evaluates player and squad performance across a multi-GW horizon (e.g. 3 to 8 Gameweeks),
detects fixture swings across Premier League clubs, and projects GW-by-GW optimal lineups.
"""
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.analysis.understat_fusion import UnderstatFusion
from src.models.analysis import (
    FixtureDetails,
    FixtureSwingItem,
    GameweekProjection,
    GameweekSquadProjection,
    MultiGWManagerReport,
    PlayerAnalysis,
    PlayerHorizonAnalysis,
    PlayerScoreBreakdown,
)
from src.models.player import UnderstatStats


class MultiGWAnalyzer:
    """Multi-Gameweek projection and fixture swing intelligence engine."""

    def __init__(self, fpl_client: Any, understat_fusion: Optional[UnderstatFusion] = None):
        """
        :param fpl_client: An instance of FPLClient
        :param understat_fusion: Optional instance of UnderstatFusion
        """
        self.client = fpl_client
        self.fusion = understat_fusion

    def get_upcoming_gameweek(self, bootstrap_data: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """Identify next upcoming Gameweek ID and deadline."""
        events = bootstrap_data.get("events", [])
        next_event = next((e for e in events if e.get("is_next")), None)
        if next_event:
            return next_event["id"], next_event.get("deadline_time")
        
        unfinished = next((e for e in events if not e.get("finished", False)), None)
        if unfinished:
            return unfinished["id"], unfinished.get("deadline_time")
        
        current_event = next((e for e in events if e.get("is_current")), None)
        if current_event and not current_event.get("finished", False):
            return current_event["id"], current_event.get("deadline_time")
            
        return 1, None

    def analyze_fixture_swings(
        self, 
        start_gw: int, 
        end_gw: int, 
        all_fixtures: List[Dict[str, Any]], 
        teams_map: Dict[int, Dict[str, Any]],
        all_elements: List[Dict[str, Any]]
    ) -> List[FixtureSwingItem]:
        """
        Analyze fixture difficulty sequences for all 20 Premier League clubs over the horizon window.
        Identifies positive fixture swings (clubs entering easy runs) and negative swings (hardening runs).
        """
        swings: List[FixtureSwingItem] = []
        
        # Group key players by team for recommendation insights
        team_key_assets: Dict[int, List[str]] = {}
        for elem in sorted(all_elements, key=lambda x: float(x.get("total_points", 0)), reverse=True):
            t_id = elem.get("team", 0)
            if t_id not in team_key_assets:
                team_key_assets[t_id] = []
            if len(team_key_assets[t_id]) < 3:
                cost = float(elem.get("now_cost", 0)) / 10.0
                team_key_assets[t_id].append(f"{elem.get('web_name')} (£{cost:.1f}m)")

        for team_id, team_obj in teams_map.items():
            fdr_seq: List[int] = []
            for gw in range(start_gw, end_gw + 1):
                gw_matches = [
                    f for f in all_fixtures 
                    if f.get("event") == gw and (f.get("team_h") == team_id or f.get("team_a") == team_id)
                ]
                if not gw_matches:
                    fdr_seq.append(3)  # Blank placeholder
                else:
                    # Average FDR if double gameweek
                    gw_diffs = [
                        (f.get("team_h_difficulty") if f.get("team_h") == team_id else f.get("team_a_difficulty")) or 3
                        for f in gw_matches
                    ]
                    fdr_seq.append(round(sum(gw_diffs) / len(gw_diffs)))

            fdr_avg = round(sum(fdr_seq) / len(fdr_seq), 2) if fdr_seq else 3.0

            # Swing score: baseline difficulty (3.0) minus fdr_avg
            # Positive score (> +0.4) means very easy schedule
            # Negative score (< -0.4) means very tough schedule
            swing_score = round(3.0 - fdr_avg, 2)

            if fdr_avg <= 2.6:
                sentiment = "Prime Target 🟢"
            elif fdr_avg >= 3.5:
                sentiment = "Toughening 🔴"
            else:
                sentiment = "Neutral ⚪"

            swings.append(
                FixtureSwingItem(
                    team_id=team_id,
                    team_name=team_obj.get("name", "Unknown"),
                    team_short_name=team_obj.get("short_name", "UNK"),
                    start_gw=start_gw,
                    end_gw=end_gw,
                    fdr_sequence=fdr_seq,
                    fdr_avg=fdr_avg,
                    swing_score=swing_score,
                    sentiment=sentiment,
                    key_assets=team_key_assets.get(team_id, [])
                )
            )

        # Sort by best fixture runs first (highest swing score)
        swings.sort(key=lambda x: x.swing_score, reverse=True)
        return swings

    def project_player_horizon(
        self,
        player_dict: Dict[str, Any],
        start_gw: int,
        end_gw: int,
        all_fixtures: List[Dict[str, Any]],
        teams_map: Dict[int, Dict[str, Any]],
        positions_map: Dict[int, Dict[str, Any]],
        understat_stats: Optional[UnderstatStats] = None
    ) -> PlayerHorizonAnalysis:
        """
        Project a single player's performance and expected points across all gameweeks in the horizon.
        """
        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer = SquadAnalyzer(self.client)

        team_id = player_dict.get("team", 0)
        team_obj = teams_map.get(team_id, {})
        elem_type_id = player_dict.get("element_type", 1)
        pos_obj = positions_map.get(elem_type_id, {})

        gw_projections: List[GameweekProjection] = []
        total_xp = 0.0
        fdr_list: List[float] = []

        for gw in range(start_gw, end_gw + 1):
            player_fixtures = analyzer.resolve_player_fixtures(team_id, gw, all_fixtures, teams_map)
            score_breakdown = analyzer.calculate_player_score(player_dict, player_fixtures, understat_stats=understat_stats)
            
            diff_avg = sum(f.difficulty for f in player_fixtures) / len(player_fixtures) if player_fixtures else 3.0
            is_blank = any(f.is_blank for f in player_fixtures)
            is_double = any(f.is_double for f in player_fixtures)

            gw_projections.append(
                GameweekProjection(
                    gameweek=gw,
                    fixtures=player_fixtures,
                    expected_points=score_breakdown.expected_points,
                    difficulty_avg=round(diff_avg, 2),
                    is_blank=is_blank,
                    is_double=is_double,
                    tags=score_breakdown.tags
                )
            )
            total_xp += score_breakdown.expected_points
            fdr_list.append(diff_avg)

        avg_fdr = round(sum(fdr_list) / len(fdr_list), 2) if fdr_list else 3.0
        if avg_fdr <= 2.6:
            rating = "Favorable 🔥"
        elif avg_fdr >= 3.6:
            rating = "Tough ⚠️"
        else:
            rating = "Mixed ⚖️"

        cost_m = round(float(player_dict.get("now_cost", 0)) / 10.0, 1)

        return PlayerHorizonAnalysis(
            element=player_dict["id"],
            web_name=player_dict.get("web_name", "Unknown"),
            first_name=player_dict.get("first_name", ""),
            second_name=player_dict.get("second_name", ""),
            team_id=team_id,
            team_name=team_obj.get("name", "Unknown"),
            team_short_name=team_obj.get("short_name", "UNK"),
            element_type=elem_type_id,
            position=pos_obj.get("singular_name_short", "UNK"),
            cost_m=cost_m,
            gw_projections=gw_projections,
            total_horizon_xp=round(total_xp, 2),
            avg_fdr=avg_fdr,
            fixture_run_rating=rating,
            understat=understat_stats
        )

    def analyze_manager_horizon(
        self,
        manager_id: int,
        horizon_length: int = 5,
        start_gw: Optional[int] = None,
        fpl_cookie: Optional[str] = None,
        use_cache: bool = True
    ) -> MultiGWManagerReport:
        """
        Run complete Multi-Gameweek Horizon analysis for a manager.
        Projects starting lineups, captaincy, bench order, and fixture swings for each GW in the window.
        """
        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer = SquadAnalyzer(self.client)

        bootstrap = self.client.get_bootstrap_static(use_cache=use_cache)
        elements_map = {e["id"]: e for e in bootstrap.get("elements", [])}
        teams_map = {t["id"]: t for t in bootstrap.get("teams", [])}
        positions_map = {et["id"]: et for et in bootstrap.get("element_types", [])}

        upcoming_gw, _ = self.get_upcoming_gameweek(bootstrap)
        s_gw = start_gw if (start_gw is not None and start_gw >= upcoming_gw) else upcoming_gw
        e_gw = min(38, s_gw + max(1, horizon_length) - 1)
        actual_horizon_len = (e_gw - s_gw) + 1

        manager_profile = self.client.get_manager(manager_id, use_cache=use_cache)
        manager_name = f"{manager_profile.get('player_first_name', '')} {manager_profile.get('player_last_name', '')}".strip()
        team_name = manager_profile.get("name", "")

        # Fetch fixtures for all GWs in the horizon
        all_fixtures = self.client.get_fixtures(event_id=None, use_cache=use_cache)

        # Build Understat mapping if fusion available
        understat_map: Dict[int, UnderstatStats] = {}
        if self.fusion:
            understat_map = self.fusion.build_fpl_understat_mapping(bootstrap.get("elements", []), teams_map)

        # Fetch manager squad picks
        picks = []
        cookie_to_use = fpl_cookie
        from src.config import FPLConfig
        if not cookie_to_use:
            cookie_to_use = FPLConfig.FPL_COOKIE

        if cookie_to_use:
            try:
                my_team_data = self.client.get_my_team(manager_id, cookie=cookie_to_use, use_cache=use_cache)
                if isinstance(my_team_data, dict) and "picks" in my_team_data:
                    picks = my_team_data["picks"]
            except Exception:
                picks = []

        if not picks:
            current_event = manager_profile.get("current_event") or 1
            squad_gw = s_gw if s_gw <= current_event else current_event
            try:
                picks_data = self.client.get_manager_picks(manager_id, squad_gw, use_cache=use_cache)
            except Exception:
                picks_data = self.client.get_manager_picks(manager_id, current_event, use_cache=use_cache)
            picks = picks_data.get("picks", [])

        # 1. Project each squad player across the horizon
        player_horizon_list: List[PlayerHorizonAnalysis] = []
        for pick in picks:
            elem_id = pick.get("element")
            elem = elements_map.get(elem_id, {})
            u_stats = understat_map.get(elem_id)
            p_horizon = self.project_player_horizon(
                elem, s_gw, e_gw, all_fixtures, teams_map, positions_map, understat_stats=u_stats
            )
            player_horizon_list.append(p_horizon)

        # 2. For each Gameweek in the horizon, calculate optimal lineup and projected xP
        gw_squad_projections: List[GameweekSquadProjection] = []
        total_squad_horizon_xp = 0.0

        for gw in range(s_gw, e_gw + 1):
            analyzed_for_gw: List[PlayerAnalysis] = []
            for pick in picks:
                elem_id = pick.get("element")
                pos_num = pick.get("position", 1)
                elem = elements_map.get(elem_id, {})
                team_id = elem.get("team", 0)
                team_obj = teams_map.get(team_id, {})
                elem_type_id = elem.get("element_type", 1)
                pos_obj = positions_map.get(elem_type_id, {})

                p_fix = analyzer.resolve_player_fixtures(team_id, gw, all_fixtures, teams_map)
                u_stats = understat_map.get(elem_id)
                score_bd = analyzer.calculate_player_score(elem, p_fix, understat_stats=u_stats)

                raw_status = elem.get("status", "a")
                chance = elem.get("chance_of_playing_next_round")
                status_str = "Available" if raw_status == "a" else (f"Doubtful ({chance}%)" if raw_status == "d" and chance else raw_status)

                p_ana = PlayerAnalysis(
                    element=elem_id,
                    web_name=elem.get("web_name", "Unknown"),
                    first_name=elem.get("first_name", ""),
                    second_name=elem.get("second_name", ""),
                    team_id=team_id,
                    team_name=team_obj.get("name", "Unknown"),
                    team_short_name=team_obj.get("short_name", "UNK"),
                    element_type=elem_type_id,
                    position=pos_obj.get("singular_name_short", "UNK"),
                    cost_m=round(float(elem.get("now_cost", 0)) / 10.0, 1),
                    total_points=int(elem.get("total_points", 0)),
                    form=float(elem.get("form", 0.0) or 0.0),
                    expected_goals=float(elem.get("expected_goals", 0.0) or 0.0),
                    expected_assists=float(elem.get("expected_assists", 0.0) or 0.0),
                    expected_goal_involvements=float(elem.get("expected_goal_involvements", 0.0) or 0.0),
                    status=status_str,
                    chance_of_playing_next_round=chance,
                    news=elem.get("news"),
                    squad_position=pos_num,
                    is_current_starter=(pos_num <= 11),
                    is_current_bench=(pos_num > 11),
                    is_current_captain=bool(pick.get("is_captain", False)),
                    is_current_vice_captain=bool(pick.get("is_vice_captain", False)),
                    fixtures=p_fix,
                    score_breakdown=score_bd,
                    understat=u_stats
                )
                analyzed_for_gw.append(p_ana)

            # Optimize for this specific GW
            opt_gw = analyzer.optimize_squad(analyzed_for_gw, target_gw=gw)
            cap = opt_gw.captain_hierarchy[0]
            vc = opt_gw.captain_hierarchy[1] if len(opt_gw.captain_hierarchy) > 1 else cap

            gw_squad_projections.append(
                GameweekSquadProjection(
                    gameweek=gw,
                    formation=opt_gw.formation,
                    starting_xi=opt_gw.recommended_starting_xi,
                    bench=opt_gw.recommended_bench,
                    captain=cap,
                    vice_captain=vc,
                    projected_xp=opt_gw.total_projected_xp
                )
            )
            total_squad_horizon_xp += opt_gw.total_projected_xp

        # 3. Analyze League-wide Fixture Swings
        fixture_swings = self.analyze_fixture_swings(
            s_gw, e_gw, all_fixtures, teams_map, bootstrap.get("elements", [])
        )

        # 4. Generate Strategic Warnings
        strategic_warnings: List[str] = []
        for p in player_horizon_list:
            if p.fixture_run_rating == "Tough ⚠️":
                strategic_warnings.append(
                    f"⚠️ Difficult Run: {p.web_name} ({p.team_short_name} - {p.position}) faces an average FDR of {p.avg_fdr:.1f} over GW {s_gw}-{e_gw}."
                )

        avg_xp_per_gw = round(total_squad_horizon_xp / actual_horizon_len, 2) if actual_horizon_len > 0 else 0.0

        return MultiGWManagerReport(
            manager_id=manager_id,
            manager_name=manager_name,
            team_name=team_name,
            start_gameweek=s_gw,
            end_gameweek=e_gw,
            horizon_length=actual_horizon_len,
            gameweek_squads=gw_squad_projections,
            player_projections=player_horizon_list,
            total_horizon_xp=round(total_squad_horizon_xp, 2),
            avg_xp_per_gw=avg_xp_per_gw,
            fixture_swings=fixture_swings[:6],  # Top 6 swings
            strategic_warnings=strategic_warnings
        )

    def get_horizon_summary_df(
        self,
        manager_id: int,
        horizon_length: int = 5,
        start_gw: Optional[int] = None,
        fpl_cookie: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Export Multi-Gameweek player projections as a tabular DataFrame.
        Columns show each player's xP for each Gameweek in the horizon and total cumulative xP.
        """
        report = self.analyze_manager_horizon(
            manager_id=manager_id, 
            horizon_length=horizon_length, 
            start_gw=start_gw, 
            fpl_cookie=fpl_cookie
        )
        rows = []
        for p in report.player_projections:
            row = {
                "Player": p.web_name,
                "Team": p.team_short_name,
                "Pos": p.position,
                "Cost": f"£{p.cost_m:.1f}m",
                "Fixture Run": p.fixture_run_rating,
                "Avg FDR": p.avg_fdr,
            }
            for proj in p.gw_projections:
                fix_str = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'})" for f in proj.fixtures])
                row[f"GW{proj.gameweek}"] = f"{proj.expected_points:.1f} ({fix_str})"
            
            row["Total xP"] = p.total_horizon_xp
            rows.append(row)

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(by="Total xP", ascending=False)
        return df
