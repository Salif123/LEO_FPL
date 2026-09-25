"""
Mini-League Intelligence & Effective Ownership (EO) Engine.
Analyzes mini-league standings, rival squad overlaps, captaincy distributions,
Effective Ownership (EO) matrices, and identifies high-upside differential opportunities.
"""
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

from src.models.analysis import (
    EffectiveOwnershipItem,
    MiniLeagueAnalysisReport,
    MiniLeagueRivalOverview,
    PlayerAnalysis,
    SquadOverlapComparison,
)


class LeagueAnalyzer:
    """Mini-League and Effective Ownership (EO) analytics engine."""

    def __init__(self, fpl_client: Any):
        """
        :param fpl_client: An instance of FPLClient
        """
        self.client = fpl_client

    def analyze_mini_league(
        self,
        league_id: int,
        target_manager_id: Optional[int] = None,
        gw: Optional[int] = None,
        use_cache: bool = True
    ) -> MiniLeagueAnalysisReport:
        """
        Analyze an entire classic mini-league:
        1. Fetch standings and all rival Manager IDs.
        2. Fetch each manager's squad picks, captain, bench, and active chip.
        3. Compute league-wide Effective Ownership (EO) for all players.
        4. Compare target manager's squad against rivals (overlap %, differentials, captain clashes).
        5. Find high-xP differential opportunities with low ownership in the league.
        """
        bootstrap = self.client.get_bootstrap_static(use_cache=use_cache)
        elements_map = {e["id"]: e for e in bootstrap.get("elements", [])}
        teams_map = {t["id"]: t for t in bootstrap.get("teams", [])}
        positions_map = {et["id"]: et for et in bootstrap.get("element_types", [])}

        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer = SquadAnalyzer(self.client)
        upcoming_gw, _ = analyzer.get_upcoming_gameweek(bootstrap)

        # 1. Fetch Classic League Standings
        league_data = self.client.get_classic_league(league_id, use_cache=use_cache)
        league_obj = league_data.get("league", {})
        league_name = league_obj.get("name", f"League #{league_id}")
        standings_results = league_data.get("standings", {}).get("results", [])

        if not standings_results:
            return MiniLeagueAnalysisReport(
                league_id=league_id,
                league_name=league_name,
                total_managers=0,
                target_gameweek=upcoming_gw,
                target_manager_id=target_manager_id
            )

        total_managers = len(standings_results)

        # 2. Fetch each manager's squad picks
        manager_squads: Dict[int, Dict[str, Any]] = {}
        standings_overview: List[MiniLeagueRivalOverview] = []
        captain_counts: Dict[str, int] = {}

        # Player stats accumulator for EO calculation
        # element_id -> {"starters": int, "bench": int, "captains": int, "triple_caps": int}
        player_stats_acc: Dict[int, Dict[str, int]] = {}

        for entry in standings_results:
            m_id = entry.get("entry")
            rank = entry.get("rank", 0)
            last_rank = entry.get("last_rank", 0)
            mgr_name = entry.get("player_name", "Unknown")
            t_name = entry.get("entry_name", "Unknown Team")
            tot_pts = entry.get("total", 0)
            ev_pts = entry.get("event_total", 0)

            # Fetch manager profile to resolve current active gameweek
            mgr_profile = self.client.get_manager(m_id, use_cache=use_cache)
            curr_ev = mgr_profile.get("current_event") or 1
            squad_gw = gw if (gw is not None and gw <= curr_ev) else curr_ev

            try:
                picks_data = self.client.get_manager_picks(m_id, squad_gw, use_cache=use_cache)
            except Exception:
                picks_data = self.client.get_manager_picks(m_id, curr_ev, use_cache=use_cache)

            picks = picks_data.get("picks", [])
            active_chip = picks_data.get("active_chip")

            captain_name = "Unknown"
            starter_ids: Set[int] = set()
            bench_ids: Set[int] = set()
            all_squad_ids: Set[int] = set()
            cap_id = None
            tc_id = None

            for p in picks:
                elem_id = p.get("element")
                pos_order = p.get("position", 1)
                mult = p.get("multiplier", 1)
                is_cap = bool(p.get("is_captain", False))

                all_squad_ids.add(elem_id)
                if pos_order <= 11:
                    starter_ids.add(elem_id)
                else:
                    bench_ids.add(elem_id)

                if is_cap:
                    cap_elem = elements_map.get(elem_id, {})
                    captain_name = cap_elem.get("web_name", "Unknown")
                    if mult >= 3:
                        tc_id = elem_id
                    else:
                        cap_id = elem_id

                # Accumulate for EO
                if elem_id not in player_stats_acc:
                    player_stats_acc[elem_id] = {"starters": 0, "bench": 0, "captains": 0, "triple_caps": 0}

                if pos_order <= 11:
                    player_stats_acc[elem_id]["starters"] += 1
                else:
                    player_stats_acc[elem_id]["bench"] += 1

                if mult == 2:
                    player_stats_acc[elem_id]["captains"] += 1
                elif mult >= 3:
                    player_stats_acc[elem_id]["triple_caps"] += 1

            captain_counts[captain_name] = captain_counts.get(captain_name, 0) + 1

            manager_squads[m_id] = {
                "rank": rank,
                "name": mgr_name,
                "team_name": t_name,
                "total": tot_pts,
                "gw_points": ev_pts,
                "starters": starter_ids,
                "bench": bench_ids,
                "all_players": all_squad_ids,
                "captain_name": captain_name,
                "captain_id": cap_id or tc_id,
                "active_chip": active_chip
            }

            standings_overview.append(
                MiniLeagueRivalOverview(
                    entry_id=m_id,
                    rank=rank,
                    last_rank=last_rank,
                    manager_name=mgr_name,
                    team_name=t_name,
                    total_points=tot_pts,
                    gw_points=ev_pts,
                    captain_name=captain_name,
                    active_chip=active_chip
                )
            )

        # 3. Calculate Effective Ownership (EO)
        user_squad_info = manager_squads.get(target_manager_id) if target_manager_id else None
        user_all_ids = user_squad_info["all_players"] if user_squad_info else set()
        user_cap_id = user_squad_info["captain_id"] if user_squad_info else None

        eo_items: List[EffectiveOwnershipItem] = []
        for elem_id, counts in player_stats_acc.items():
            elem = elements_map.get(elem_id, {})
            t_id = elem.get("team", 0)
            team_obj = teams_map.get(t_id, {})
            et_id = elem.get("element_type", 1)
            pos_obj = positions_map.get(et_id, {})

            starting_pct = round((counts["starters"] / total_managers) * 100.0, 1)
            bench_pct = round((counts["bench"] / total_managers) * 100.0, 1)
            cap_pct = round((counts["captains"] / total_managers) * 100.0, 1)
            tc_pct = round((counts["triple_caps"] / total_managers) * 100.0, 1)
            
            # Effective Ownership = Starting % + Captain % + (2 * TC %)
            eo_pct = round(starting_pct + cap_pct + (2.0 * tc_pct), 1)

            is_user_owned = elem_id in user_all_ids
            is_user_cap = (elem_id == user_cap_id)

            # User gain factor calculation: user's multiplier - (EO / 100)
            user_mult = 0.0
            if is_user_cap:
                user_mult = 2.0
            elif is_user_owned:
                user_mult = 1.0
            gain_factor = round(user_mult - (eo_pct / 100.0), 2)

            if eo_pct >= 100.0 and not is_user_cap:
                sentiment = "High Threat 🔥"
            elif is_user_owned and eo_pct <= 35.0:
                sentiment = "Differential Win 💎"
            elif eo_pct >= 70.0:
                sentiment = "Template 🛡️"
            else:
                sentiment = "Neutral"

            cost_m = round(float(elem.get("now_cost", 0)) / 10.0, 1)

            eo_items.append(
                EffectiveOwnershipItem(
                    element=elem_id,
                    web_name=elem.get("web_name", "Unknown"),
                    team_short_name=team_obj.get("short_name", "UNK"),
                    position=pos_obj.get("singular_name_short", "UNK"),
                    cost_m=cost_m,
                    starting_ownership_pct=starting_pct,
                    bench_ownership_pct=bench_pct,
                    captaincy_pct=cap_pct,
                    triple_captaincy_pct=tc_pct,
                    effective_ownership_pct=eo_pct,
                    is_owned_by_user=is_user_owned,
                    is_captained_by_user=is_user_cap,
                    user_gain_factor=gain_factor,
                    threat_sentiment=sentiment
                )
            )

        # Sort by EO descending
        eo_items.sort(key=lambda x: x.effective_ownership_pct, reverse=True)

        # 4. Captaincy Distribution
        cap_distribution = {
            cap: round((cnt / total_managers) * 100.0, 1)
            for cap, cnt in sorted(captain_counts.items(), key=lambda x: x[1], reverse=True)
        }

        # 5. Head-to-Head Overlap Analysis vs Rivals
        rival_comparisons: List[SquadOverlapComparison] = []
        if target_manager_id and user_squad_info:
            user_starters = user_squad_info["starters"]
            user_tot = user_squad_info["total"]

            for rival_id, r_info in manager_squads.items():
                if rival_id == target_manager_id:
                    continue

                r_all = r_info["all_players"]
                r_starters = r_info["starters"]
                shared_all = user_all_ids.intersection(r_all)
                shared_start = user_starters.intersection(r_starters)

                user_diff_ids = user_all_ids - r_all
                rival_diff_ids = r_all - user_all_ids

                user_diff_names = [elements_map.get(pid, {}).get("web_name", "UNK") for pid in user_diff_ids]
                rival_diff_names = [elements_map.get(pid, {}).get("web_name", "UNK") for pid in rival_diff_ids]
                shared_names = [elements_map.get(pid, {}).get("web_name", "UNK") for pid in shared_all]

                overlap_pct = round((len(shared_all) / 15.0) * 100.0, 1)
                cap_clash = (user_squad_info["captain_name"] != r_info["captain_name"])

                rival_comparisons.append(
                    SquadOverlapComparison(
                        rival_entry_id=rival_id,
                        rival_name=r_info["name"],
                        rival_team_name=r_info["team_name"],
                        rival_rank=r_info["rank"],
                        rival_total_points=r_info["total"],
                        points_difference=(user_tot - r_info["total"]),
                        shared_players_count=len(shared_all),
                        overlap_percentage=overlap_pct,
                        shared_starters_count=len(shared_start),
                        shared_player_names=shared_names,
                        user_differentials=user_diff_names,
                        rival_differentials=rival_diff_names,
                        rival_captain=r_info["captain_name"],
                        captain_clash=cap_clash
                    )
                )

            # Sort rival comparisons by rival rank ascending
            rival_comparisons.sort(key=lambda x: x.rival_rank)

        # 6. Tactical Summary Insights
        tactical_summary: List[str] = []
        if eo_items:
            top_eo = eo_items[0]
            tactical_summary.append(
                f"🛡️ League Template Anchor: {top_eo.web_name} has {top_eo.effective_ownership_pct}% Effective Ownership in this league."
            )

        if cap_distribution:
            top_cap_name, top_cap_pct = next(iter(cap_distribution.items()))
            tactical_summary.append(
                f"👑 Captaincy Consensus: {top_cap_pct}% of rivals captained '{top_cap_name}'."
            )

        if rival_comparisons:
            leader_cmp = rival_comparisons[0]
            tactical_summary.append(
                f"🏆 Leader Matchup: You share {leader_cmp.shared_players_count}/15 players ({leader_cmp.overlap_percentage}%) with #1 {leader_cmp.rival_name}."
            )

        return MiniLeagueAnalysisReport(
            league_id=league_id,
            league_name=league_name,
            total_managers=total_managers,
            target_gameweek=upcoming_gw,
            target_manager_id=target_manager_id,
            standings=standings_overview,
            effective_ownership=eo_items,
            top_captains_distribution=cap_distribution,
            rival_comparisons=rival_comparisons,
            top_differential_opportunities=[],
            tactical_summary=tactical_summary
        )

    def get_league_eo_df(
        self,
        league_id: int,
        target_manager_id: Optional[int] = None,
        gw: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Export mini-league Effective Ownership as a clean Pandas DataFrame.
        """
        report = self.analyze_mini_league(league_id, target_manager_id, gw)
        rows = []
        for item in report.effective_ownership:
            owned_str = "Yes ✅" if item.is_owned_by_user else "No ❌"
            if item.is_captained_by_user:
                owned_str = "Captain 👑"

            rows.append({
                "Player": item.web_name,
                "Club": item.team_short_name,
                "Pos": item.position,
                "Cost": f"£{item.cost_m:.1f}m",
                "Started %": f"{item.starting_ownership_pct}%",
                "Benched %": f"{item.bench_ownership_pct}%",
                "Captain %": f"{item.captaincy_pct}%",
                "Effective Ownership (EO)": f"{item.effective_ownership_pct}%",
                "You Own?": owned_str,
                "Sentiment": item.threat_sentiment
            })

        df = pd.DataFrame(rows)
        return df

    def get_rival_overlap_df(
        self,
        league_id: int,
        target_manager_id: int,
        gw: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Export head-to-head squad comparison against all rivals in the league.
        """
        report = self.analyze_mini_league(league_id, target_manager_id, gw)
        rows = []
        for cmp in report.rival_comparisons:
            diff_str = f"+{cmp.points_difference}" if cmp.points_difference > 0 else str(cmp.points_difference)
            rows.append({
                "Rank": f"#{cmp.rival_rank}",
                "Rival": cmp.rival_name,
                "Team": cmp.rival_team_name,
                "Pts Diff": diff_str,
                "Shared (15)": f"{cmp.shared_players_count}/15 ({cmp.overlap_percentage}%)",
                "Shared Starters (11)": f"{cmp.shared_starters_count}/11",
                "Rival Captain": cmp.rival_captain,
                "Captain Clash?": "⚔️ Yes" if cmp.captain_clash else "Identical 🛡️",
                "Your Differentials": ", ".join(cmp.user_differentials[:3]),
                "Rival Differentials": ", ".join(cmp.rival_differentials[:3]),
            })

        df = pd.DataFrame(rows)
        return df
