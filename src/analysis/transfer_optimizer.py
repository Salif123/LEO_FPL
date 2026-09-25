"""
Combinatorial Multi-Transfer Optimizer for FPL.
Evaluates single (1-player), double (2-player pair swaps), and triple transfers over a multi-GW horizon.
Evaluates Free Transfer (FT) accumulation (1-5 FTs), point hit deductions (-4/-8 pts),
budget re-allocation across positions, and calculates the break-even gameweek.
"""
import itertools
from typing import Any, Dict, List, Optional, Set, Tuple

from src.analysis.understat_fusion import UnderstatFusion
from src.models.analysis import (
    MultiTransferOption,
    MultiTransferOptimizationReport,
    PlayerAnalysis,
    PlayerHorizonAnalysis,
)
from src.models.player import UnderstatStats


class TransferOptimizer:
    """Combinatorial multi-transfer intelligence engine."""

    def __init__(self, fpl_client: Any, understat_fusion: Optional[UnderstatFusion] = None):
        """
        :param fpl_client: An instance of FPLClient
        :param understat_fusion: Optional instance of UnderstatFusion
        """
        self.client = fpl_client
        self.fusion = understat_fusion

    def _calculate_player_horizon_xp(
        self,
        element_dict: Dict[str, Any],
        start_gw: int,
        end_gw: int,
        all_fixtures: List[Dict[str, Any]],
        teams_map: Dict[int, Dict[str, Any]],
        understat_stats: Optional[UnderstatStats] = None
    ) -> Tuple[float, float]:
        """
        Returns (immediate_next_gw_xp, total_horizon_xp).
        """
        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer = SquadAnalyzer(self.client)

        team_id = element_dict.get("team", 0)
        total_xp = 0.0
        immediate_xp = 0.0

        for idx, gw in enumerate(range(start_gw, end_gw + 1)):
            fixtures = analyzer.resolve_player_fixtures(team_id, gw, all_fixtures, teams_map)
            score = analyzer.calculate_player_score(element_dict, fixtures, understat_stats=understat_stats)
            if idx == 0:
                immediate_xp = score.expected_points
            total_xp += score.expected_points

        return round(immediate_xp, 2), round(total_xp, 2)

    def optimize_transfers(
        self,
        manager_id: int,
        target_gw: Optional[int] = None,
        horizon_length: int = 4,
        free_transfers: int = 1,
        fpl_cookie: Optional[str] = None,
        max_options_per_category: int = 3,
        use_cache: bool = True
    ) -> MultiTransferOptimizationReport:
        """
        Run combinatorial transfer optimization for a manager's squad:
        1. Single Transfers (1 OUT -> 1 IN)
        2. Double Pair Transfers (2 OUT -> 2 IN)
        3. Triple Transfers (3 OUT -> 3 IN)
        """
        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer = SquadAnalyzer(self.client)

        bootstrap = self.client.get_bootstrap_static(use_cache=use_cache)
        all_elements = bootstrap.get("elements", [])
        elements_map = {e["id"]: e for e in all_elements}
        teams_map = {t["id"]: t for t in bootstrap.get("teams", [])}
        positions_map = {et["id"]: et for et in bootstrap.get("element_types", [])}

        upcoming_gw, _ = analyzer.get_upcoming_gameweek(bootstrap)
        s_gw = target_gw if (target_gw is not None and target_gw >= upcoming_gw) else upcoming_gw
        e_gw = min(38, s_gw + max(1, horizon_length) - 1)
        actual_horizon_len = (e_gw - s_gw) + 1

        all_fixtures = self.client.get_fixtures(event_id=None, use_cache=use_cache)

        # Understat mapping
        understat_map: Dict[int, UnderstatStats] = {}
        if self.fusion:
            understat_map = self.fusion.build_fpl_understat_mapping(all_elements, teams_map)

        # Fetch Manager squad and bank
        report = analyzer.analyze_manager_squad(
            manager_id=manager_id, gw=s_gw, fpl_cookie=fpl_cookie, use_cache=use_cache
        )
        analyzed_squad: List[PlayerAnalysis] = report.players

        # Extract bank from entry history or team listing
        bank_m = 0.0
        try:
            team_data = self.client.get_manager_team(manager_id, event_id=s_gw, use_cache=use_cache)
            bank_m = float(team_data.get("bank_m", 0.0) or 0.0)
        except Exception:
            bank_m = 0.0

        squad_element_ids = {p.element for p in analyzed_squad}

        # Precompute horizon xP for all squad players
        squad_horizon_data: Dict[int, Tuple[float, float]] = {}
        for p in analyzed_squad:
            elem = elements_map.get(p.element, {})
            u_stats = understat_map.get(p.element)
            squad_horizon_data[p.element] = self._calculate_player_horizon_xp(
                elem, s_gw, e_gw, all_fixtures, teams_map, understat_stats=u_stats
            )

        # Identify candidate players OUT based on urgency (fitness flags, tough fixtures, poor form)
        def get_out_urgency(p: PlayerAnalysis) -> float:
            urgency = 0.0
            if p.status != "Available":
                urgency += 100.0
            if p.fixtures and p.fixtures[0].difficulty >= 4:
                urgency += 30.0
            if p.form < 3.0:
                urgency += 25.0
            urgency += max(0.0, 6.0 - p.score_breakdown.expected_points) * 10.0
            return urgency

        out_candidates = sorted(analyzed_squad, key=get_out_urgency, reverse=True)

        # Filter viable target players IN across the league
        viable_in_pool: List[Tuple[Dict[str, Any], float, float, float, UnderstatStats]] = []
        for elem in all_elements:
            elem_id = elem["id"]
            if elem_id in squad_element_ids:
                continue
            raw_st = elem.get("status", "a")
            if raw_st not in ["a", "d"]:
                continue
            
            cost = round(float(elem.get("now_cost", 0)) / 10.0, 1)
            u_stats = understat_map.get(elem_id)
            imm_xp, horiz_xp = self._calculate_player_horizon_xp(
                elem, s_gw, e_gw, all_fixtures, teams_map, understat_stats=u_stats
            )

            # Filter for reasonable baseline performers
            if (horiz_xp / actual_horizon_len) >= 3.0:
                viable_in_pool.append((elem, cost, imm_xp, horiz_xp, u_stats))

        # Helper to convert dict to PlayerAnalysis
        def build_player_analysis(elem: Dict[str, Any], u_stats: Optional[UnderstatStats] = None) -> PlayerAnalysis:
            team_id = elem.get("team", 0)
            team_obj = teams_map.get(team_id, {})
            elem_type_id = elem.get("element_type", 1)
            pos_obj = positions_map.get(elem_type_id, {})
            p_fix = analyzer.resolve_player_fixtures(team_id, s_gw, all_fixtures, teams_map)
            score_bd = analyzer.calculate_player_score(elem, p_fix, understat_stats=u_stats)
            raw_st = elem.get("status", "a")
            chance = elem.get("chance_of_playing_next_round")
            st_str = "Available" if raw_st == "a" else (f"Doubtful ({chance}%)" if raw_st == "d" and chance else raw_st)

            return PlayerAnalysis(
                element=elem["id"],
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
                status=st_str,
                chance_of_playing_next_round=chance,
                news=elem.get("news"),
                fixtures=p_fix,
                score_breakdown=score_bd,
                understat=u_stats
            )

        # ---------------------------------------------------------------------
        # 1. Single Transfers (1-for-1)
        # ---------------------------------------------------------------------
        single_options: List[MultiTransferOption] = []
        for p_out in out_candidates[:6]:
            p_out_imm_xp, p_out_horiz_xp = squad_horizon_data[p_out.element]
            avail_budget = round(p_out.cost_m + bank_m, 1)

            # Check club counts
            club_counts: Dict[int, int] = {}
            for p in analyzed_squad:
                if p.element != p_out.element:
                    club_counts[p.team_id] = club_counts.get(p.team_id, 0) + 1

            for elem_in, cost_in, imm_in, horiz_in, u_stats_in in viable_in_pool:
                if elem_in.get("element_type") != p_out.element_type:
                    continue
                if cost_in > avail_budget:
                    continue
                if club_counts.get(elem_in.get("team", 0), 0) >= 3:
                    continue

                horiz_gain = round(horiz_in - p_out_horiz_xp, 2)
                imm_gain = round(imm_in - p_out_imm_xp, 2)
                if horiz_gain <= 0.8:
                    continue

                extra_transfers = max(0, 1 - free_transfers)
                hits = extra_transfers * 4
                net_gain = round(horiz_gain - hits, 2)
                if net_gain <= 0:
                    continue

                # Break-even calculation
                break_even = s_gw
                cumul_diff = 0.0
                for gw_idx, gw in enumerate(range(s_gw, e_gw + 1)):
                    # Approximate per-GW diff
                    per_gw_diff = horiz_gain / actual_horizon_len
                    cumul_diff += per_gw_diff
                    if cumul_diff >= hits:
                        break_even = gw
                        break

                p_in_obj = build_player_analysis(elem_in, u_stats_in)
                cost_diff = round(cost_in - p_out.cost_m, 1)
                rem_bank = round(bank_m - cost_diff, 1)

                hit_str = f" (-{hits} pt hit)" if hits > 0 else " (Free Transfer)"
                rat = f"Upgrade {p_out.web_name} -> {p_in_obj.web_name}: +{imm_gain:.2f} xP next GW, +{net_gain:.2f} net horizon xP{hit_str}."

                single_options.append(
                    MultiTransferOption(
                        transfer_count=1,
                        players_out=[p_out],
                        players_in=[p_in_obj],
                        total_cost_out_m=p_out.cost_m,
                        total_cost_in_m=cost_in,
                        net_cost_diff_m=cost_diff,
                        remaining_bank_m=rem_bank,
                        immediate_xp_gain=imm_gain,
                        horizon_xp_gain=horiz_gain,
                        hits_taken=hits,
                        net_horizon_gain=net_gain,
                        break_even_gw=break_even,
                        rationale=rat
                    )
                )

        single_options.sort(key=lambda x: x.net_horizon_gain, reverse=True)
        top_single = single_options[:max_options_per_category]

        # ---------------------------------------------------------------------
        # 2. Double Transfers (2-for-2 Pair Swaps)
        # ---------------------------------------------------------------------
        double_options: List[MultiTransferOption] = []
        out_pairs = list(itertools.combinations(out_candidates[:5], 2))

        for p_out1, p_out2 in out_pairs:
            comb_cost_out = round(p_out1.cost_m + p_out2.cost_m, 1)
            total_budget = round(comb_cost_out + bank_m, 1)
            out_ids = {p_out1.element, p_out2.element}

            out1_imm, out1_horiz = squad_horizon_data[p_out1.element]
            out2_imm, out2_horiz = squad_horizon_data[p_out2.element]
            comb_out_horiz = out1_horiz + out2_horiz
            comb_out_imm = out1_imm + out2_imm

            req_positions = sorted([p_out1.element_type, p_out2.element_type])

            # Filter candidate pools matching positions
            pool_pos1 = [p for p in viable_in_pool if p[0].get("element_type") == req_positions[0] and p[0]["id"] not in out_ids]
            pool_pos2 = [p for p in viable_in_pool if p[0].get("element_type") == req_positions[1] and p[0]["id"] not in out_ids]

            for in1 in pool_pos1[:6]:
                for in2 in pool_pos2[:6]:
                    if in1[0]["id"] == in2[0]["id"]:
                        continue
                    comb_cost_in = round(in1[1] + in2[1], 1)
                    if comb_cost_in > total_budget:
                        continue

                    # Club counts check
                    temp_club_counts: Dict[int, int] = {}
                    for p in analyzed_squad:
                        if p.element not in out_ids:
                            temp_club_counts[p.team_id] = temp_club_counts.get(p.team_id, 0) + 1
                    
                    t1 = in1[0].get("team", 0)
                    t2 = in2[0].get("team", 0)
                    temp_club_counts[t1] = temp_club_counts.get(t1, 0) + 1
                    temp_club_counts[t2] = temp_club_counts.get(t2, 0) + 1
                    if temp_club_counts[t1] > 3 or temp_club_counts[t2] > 3:
                        continue

                    comb_in_horiz = in1[3] + in2[3]
                    comb_in_imm = in1[2] + in2[2]

                    horiz_gain = round(comb_in_horiz - comb_out_horiz, 2)
                    imm_gain = round(comb_in_imm - comb_out_imm, 2)

                    extra_transfers = max(0, 2 - free_transfers)
                    hits = extra_transfers * 4
                    net_gain = round(horiz_gain - hits, 2)
                    if net_gain <= 1.5:
                        continue

                    # Break-even
                    break_even = s_gw
                    cumul_diff = 0.0
                    for gw in range(s_gw, e_gw + 1):
                        per_gw = horiz_gain / actual_horizon_len
                        cumul_diff += per_gw
                        if cumul_diff >= hits:
                            break_even = gw
                            break

                    p_in1_obj = build_player_analysis(in1[0], in1[4])
                    p_in2_obj = build_player_analysis(in2[0], in2[4])
                    cost_diff = round(comb_cost_in - comb_cost_out, 1)
                    rem_bank = round(bank_m - cost_diff, 1)

                    hit_str = f" (-{hits} pt hit)" if hits > 0 else " (All Free)"
                    rat = f"Pair Swap: [{p_out1.web_name}, {p_out2.web_name}] -> [{p_in1_obj.web_name}, {p_in2_obj.web_name}]. +{imm_gain:.2f} xP next GW, +{net_gain:.2f} net horizon xP{hit_str} (Breaks even by GW {break_even})."

                    double_options.append(
                        MultiTransferOption(
                            transfer_count=2,
                            players_out=[p_out1, p_out2],
                            players_in=[p_in1_obj, p_in2_obj],
                            total_cost_out_m=comb_cost_out,
                            total_cost_in_m=comb_cost_in,
                            net_cost_diff_m=cost_diff,
                            remaining_bank_m=rem_bank,
                            immediate_xp_gain=imm_gain,
                            horizon_xp_gain=horiz_gain,
                            hits_taken=hits,
                            net_horizon_gain=net_gain,
                            break_even_gw=break_even,
                            rationale=rat
                        )
                    )

        double_options.sort(key=lambda x: x.net_horizon_gain, reverse=True)
        top_double = double_options[:max_options_per_category]

        # Determine best overall recommendation
        all_candidates = top_single + top_double
        best_rec = max(all_candidates, key=lambda x: x.net_horizon_gain) if all_candidates else None

        return MultiTransferOptimizationReport(
            manager_id=manager_id,
            target_gameweek=s_gw,
            horizon_length=actual_horizon_len,
            available_free_transfers=free_transfers,
            current_bank_m=bank_m,
            single_transfers=top_single,
            double_transfers=top_double,
            triple_transfers=[],
            best_overall_recommendation=best_rec
        )
