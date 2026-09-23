"""
FPL Squad Analyzer & Predictive Scoring Engine.
Evaluates upcoming gameweek fixtures, home/away advantage, fixture difficulty ratings (FDR),
player form, xG/xA/xGI, and health status to compute Expected Points (xP), composite scores (0-100),
and optimal starting XI / bench lineup recommendations.
"""
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.models.analysis import (
    FixtureDetails,
    PlayerScoreBreakdown,
    PlayerAnalysis,
    CaptainChoice,
    TransferRecommendation,
    BenchComparisonItem,
    SquadOptimization,
    ManagerSquadAnalysisReport,
)


class SquadAnalyzer:
    """Core intelligence engine for evaluating manager squads and player matchday projections."""

    def __init__(self, fpl_client: Any):
        """
        :param fpl_client: An instance of FPLClient
        """
        self.client = fpl_client

    def get_upcoming_gameweek(self, bootstrap_data: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """
        Identify the next active/upcoming Gameweek ID and deadline from bootstrap events.
        Ensures past finished Gameweeks are strictly excluded.
        """
        events = bootstrap_data.get("events", [])
        
        # 1. First priority: event explicitly marked 'is_next'
        next_event = next((e for e in events if e.get("is_next")), None)
        if next_event:
            return next_event["id"], next_event.get("deadline_time")
        
        # 2. Second priority: first event that is not finished
        unfinished = next((e for e in events if not e.get("finished", False)), None)
        if unfinished:
            return unfinished["id"], unfinished.get("deadline_time")
        
        # 3. Third priority: current event if not finished
        current_event = next((e for e in events if e.get("is_current")), None)
        if current_event and not current_event.get("finished", False):
            return current_event["id"], current_event.get("deadline_time")
        
        return 1, None

    def resolve_player_fixtures(
        self, 
        team_id: int, 
        target_gw: int, 
        fixtures: List[Dict[str, Any]], 
        teams_map: Dict[int, Dict[str, Any]]
    ) -> List[FixtureDetails]:
        """
        Extract fixture(s) for a given team in the target Gameweek.
        Handles Normal (1 match), Blank (0 matches), and Double (2+ matches) gameweeks.
        """
        gw_fixtures = [
            f for f in fixtures 
            if f.get("event") == target_gw and (f.get("team_h") == team_id or f.get("team_a") == team_id)
        ]

        if not gw_fixtures:
            # Blank Gameweek for this club
            return [
                FixtureDetails(
                    gameweek=target_gw,
                    opponent_team_id=0,
                    opponent_name="BLANK",
                    opponent_short_name="BLANK",
                    is_home=False,
                    difficulty=3,
                    is_blank=True,
                    is_double=False,
                )
            ]

        results = []
        is_double = len(gw_fixtures) > 1
        for f in gw_fixtures:
            is_home = (f.get("team_h") == team_id)
            opp_id = f.get("team_a") if is_home else f.get("team_h")
            opp_obj = teams_map.get(opp_id, {})
            difficulty = f.get("team_h_difficulty") if is_home else f.get("team_a_difficulty")
            
            results.append(
                FixtureDetails(
                    gameweek=target_gw,
                    opponent_team_id=opp_id,
                    opponent_name=opp_obj.get("name", "Unknown"),
                    opponent_short_name=opp_obj.get("short_name", "UNK"),
                    is_home=is_home,
                    difficulty=difficulty or 3,
                    kickoff_time=f.get("kickoff_time"),
                    is_blank=False,
                    is_double=is_double,
                )
            )
        return results

    def calculate_player_score(
        self, 
        player_dict: Dict[str, Any], 
        fixtures: List[FixtureDetails]
    ) -> PlayerScoreBreakdown:
        """
        Calculate Expected Points (xP) and 0-100 Score for a player in the target Gameweek.
        """
        # 1. Base Form and PPG Metrics
        form_val = float(player_dict.get("form", 0.0) or 0.0)
        ppg_val = float(player_dict.get("points_per_game", 0.0) or 0.0)
        xg_val = float(player_dict.get("expected_goals", 0.0) or 0.0)
        xa_val = float(player_dict.get("expected_assists", 0.0) or 0.0)
        xgi_val = float(player_dict.get("expected_goal_involvements", 0.0) or 0.0)
        elem_type = int(player_dict.get("element_type", 1))

        # Base performance baseline (blended Form + PPG)
        form_component = 0.65 * form_val + 0.35 * ppg_val
        if form_component <= 0:
            form_component = ppg_val if ppg_val > 0 else 1.5

        # Position-specific underlying stats contribution
        if elem_type in [1, 2]:  # GKP / DEF
            # Clean sheet / defensive output proxy
            threat_component = form_component * 0.9 + (xg_val * 1.5 + xa_val * 1.0)
        else:  # MID / FWD
            # Attacking threat output proxy
            threat_component = form_component * 0.8 + (xg_val * 2.0 + xa_val * 1.5 + xgi_val * 0.5)

        baseline_raw = (form_component * 0.45) + (threat_component * 0.55)

        # 2. Fixture Multiplier & Home/Away advantage calculation
        if not fixtures or fixtures[0].is_blank:
            # Blank gameweek: 0 expected points
            return PlayerScoreBreakdown(
                base_form=form_val,
                form_component=round(form_component, 2),
                xg_xa_component=round(threat_component, 2),
                fixture_multiplier=0.0,
                home_away_multiplier=0.0,
                availability_rate=0.0,
                expected_points=0.0,
                composite_score=0.0,
                tags=["Blank Gameweek (No Fixture)"]
            )

        fdr_weights = {1: 1.28, 2: 1.15, 3: 1.00, 4: 0.85, 5: 0.70}
        
        total_xp = 0.0
        fdr_mult_sum = 0.0
        home_mult_sum = 0.0
        tags: List[str] = []

        # 3. Availability and Injury Penalty
        raw_status = player_dict.get("status", "a")
        chance = player_dict.get("chance_of_playing_next_round")
        
        if raw_status == "a":
            avail_rate = 1.0
        elif raw_status == "d":
            avail_rate = (chance / 100.0) if chance is not None else 0.75
            tags.append(f"Doubtful ({int(avail_rate * 100)}% chance)")
        elif raw_status in ["i", "s", "u", "n"]:
            avail_rate = 0.0
            tags.append("Injured / Suspended (0% chance)")
        else:
            avail_rate = 1.0

        for fix in fixtures:
            fdr_mult = fdr_weights.get(fix.difficulty, 1.0)
            home_mult = 1.10 if fix.is_home else 0.92
            
            fdr_mult_sum += fdr_mult
            home_mult_sum += home_mult

            # Fixture tags
            loc_str = "H" if fix.is_home else "A"
            if fix.difficulty <= 2:
                tags.append(f"Easy Fixture: vs {fix.opponent_short_name} ({loc_str})")
            elif fix.difficulty >= 4:
                tags.append(f"Tough Fixture: vs {fix.opponent_short_name} ({loc_str})")

            match_xp = baseline_raw * fdr_mult * home_mult * avail_rate
            total_xp += match_xp

        avg_fdr_mult = round(fdr_mult_sum / len(fixtures), 2)
        avg_home_mult = round(home_mult_sum / len(fixtures), 2)

        if len(fixtures) > 1:
            tags.append("Double Gameweek 🔥")

        if form_val >= 6.0:
            tags.append("In Form 🔥")
        if xg_val >= 2.0 or xgi_val >= 3.0:
            tags.append("High Goal Threat ⚡")

        # Cap and format Expected Points (xP)
        final_xp = round(max(0.0, total_xp), 2)
        
        # Composite score scaled to 0 - 100
        # Normal high-tier xP for a single GW is ~8.5 to 10.0 pts (Haaland / Salah in prime)
        composite_score = round(min(100.0, (final_xp / 10.5) * 100.0), 1)

        if final_xp >= 6.5 and avail_rate >= 0.75:
            tags.insert(0, "Captain Candidate 👑")

        return PlayerScoreBreakdown(
            base_form=form_val,
            form_component=round(form_component, 2),
            xg_xa_component=round(threat_component, 2),
            fixture_multiplier=avg_fdr_mult,
            home_away_multiplier=avg_home_mult,
            availability_rate=avail_rate,
            expected_points=final_xp,
            composite_score=composite_score,
            tags=list(dict.fromkeys(tags))  # unique tags
        )

    def optimize_squad(self, analyzed_players: List[PlayerAnalysis]) -> SquadOptimization:
        """
        Determine the mathematically optimal Starting XI (1 GKP + 10 Outfield conforming to valid
        FPL formations: min 3 DEF, min 2 MID, min 1 FWD), best Bench order (Subs 1-4), and Captaincy.
        """
        # Group players by element_type / position
        gkps = [p for p in analyzed_players if p.element_type == 1]
        defs = [p for p in analyzed_players if p.element_type == 2]
        mids = [p for p in analyzed_players if p.element_type == 3]
        fwds = [p for p in analyzed_players if p.element_type == 4]

        # Sort each positional pool by expected points descending
        gkps.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)
        defs.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)
        mids.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)
        fwds.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)

        best_gkp = gkps[0] if gkps else analyzed_players[0]
        backup_gkp = gkps[1] if len(gkps) > 1 else None

        # Valid FPL Outfield Formations (DEF, MID, FWD summing to 10):
        # DEF in [3, 4, 5], MID in [2, 3, 4, 5], FWD in [1, 2, 3]
        valid_formations = [
            (3, 5, 2), (3, 4, 3), (4, 4, 2), (4, 3, 3),
            (4, 5, 1), (5, 3, 2), (5, 4, 1), (5, 2, 3)
        ]

        best_formation_str = "3-4-3"
        best_starters: List[PlayerAnalysis] = []
        max_total_xp = -1.0

        for n_def, n_mid, n_fwd in valid_formations:
            if len(defs) >= n_def and len(mids) >= n_mid and len(fwds) >= n_fwd:
                selected = [best_gkp] + defs[:n_def] + mids[:n_mid] + fwds[:n_fwd]
                total_xp = sum(p.score_breakdown.expected_points for p in selected)
                if total_xp > max_total_xp:
                    max_total_xp = total_xp
                    best_formation_str = f"{n_def}-{n_mid}-{n_fwd}"
                    best_starters = selected

        # If fallback needed
        if not best_starters:
            best_starters = analyzed_players[:11]

        # Remaining outfield players go to bench
        bench_outfield = [p for p in analyzed_players if p not in best_starters and p != backup_gkp]
        # Sort bench outfield in descending order of expected points (Sub 1, Sub 2, Sub 3)
        bench_outfield.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)

        # Full bench: Sub 1, Sub 2, Sub 3 + Backup GKP
        best_bench: List[PlayerAnalysis] = bench_outfield.copy()
        if backup_gkp:
            best_bench.append(backup_gkp)

        # Mark recommended roles
        for p in best_starters:
            p.is_recommended_starter = True
            p.recommended_role = "Starting XI"

        for idx, p in enumerate(best_bench):
            p.is_recommended_starter = False
            if p.element_type == 1:
                p.recommended_role = "Bench GK"
            else:
                p.recommended_role = f"Sub {idx + 1}"

    def generate_captain_hierarchy(self, starting_xi: List[PlayerAnalysis]) -> List[CaptainChoice]:
        """
        Build the Top 3 Captaincy Hierarchy with deterministic metric-based rationale.
        """
        sorted_starters = sorted(starting_xi, key=lambda x: x.score_breakdown.expected_points, reverse=True)
        hierarchy: List[CaptainChoice] = []

        # 1. Primary Captain (Rank 1)
        c1 = sorted_starters[0]
        c1_fix = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'} - FDR {f.difficulty})" for f in c1.fixtures])
        c1_rat = f"Highest projected xP ({c1.score_breakdown.expected_points:.2f}) | Form: {c1.form:.1f} | xGI: {c1.expected_goal_involvements:.2f} vs {c1_fix}."
        hierarchy.append(
            CaptainChoice(
                rank=1,
                role_name="Primary Captain (C)",
                player=c1,
                expected_points=c1.score_breakdown.expected_points,
                threat_index=c1.score_breakdown.composite_score,
                rationale=c1_rat
            )
        )

        # 2. Vice-Captain (Rank 2)
        if len(sorted_starters) > 1:
            c2 = sorted_starters[1]
            c2_fix = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'} - FDR {f.difficulty})" for f in c2.fixtures])
            c2_rat = f"Solid floor backup ({c2.score_breakdown.expected_points:.2f} xP, Form: {c2.form:.1f}) vs {c2_fix}."
            hierarchy.append(
                CaptainChoice(
                    rank=2,
                    role_name="Vice-Captain (VC)",
                    player=c2,
                    expected_points=c2.score_breakdown.expected_points,
                    threat_index=c2.score_breakdown.composite_score,
                    rationale=c2_rat
                )
            )

        # 3. Alternative / Differential (Rank 3)
        if len(sorted_starters) > 2:
            c3 = sorted_starters[2]
            c3_fix = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'} - FDR {f.difficulty})" for f in c3.fixtures])
            c3_rat = f"High-ceiling alternative ({c3.score_breakdown.expected_points:.2f} xP, Threat: {c3.score_breakdown.composite_score}/100) vs {c3_fix}."
            hierarchy.append(
                CaptainChoice(
                    rank=3,
                    role_name="Alternative / Differential",
                    player=c3,
                    expected_points=c3.score_breakdown.expected_points,
                    threat_index=c3.score_breakdown.composite_score,
                    rationale=c3_rat
                )
            )

        return hierarchy

    def generate_transfer_recommendations(
        self,
        analyzed_players: List[PlayerAnalysis],
        all_elements: List[Dict[str, Any]],
        teams_map: Dict[int, Dict[str, Any]],
        positions_map: Dict[int, Dict[str, Any]],
        fixtures: List[Dict[str, Any]],
        target_gw: int,
        bank_m: float = 0.0,
        max_recommendations: int = 3
    ) -> List[TransferRecommendation]:
        """
        Generate metric-driven Transfer In / Transfer Out recommendations.
        Identifies struggling / injured squad players and finds the highest xP replacements
        in the Premier League within budget and club limits.
        """
        squad_element_ids = {p.element for p in analyzed_players}
        
        # Calculate urgency score for Transfer OUT candidates
        def calculate_out_urgency(p: PlayerAnalysis) -> float:
            urgency = 0.0
            if p.status != "Available":
                if p.chance_of_playing_next_round is not None:
                    urgency += (100 - p.chance_of_playing_next_round) * 1.5
                else:
                    urgency += 120.0
            if p.fixtures and p.fixtures[0].difficulty >= 4:
                urgency += (p.fixtures[0].difficulty - 3) * 20.0
            urgency += max(0.0, 5.0 - p.score_breakdown.expected_points) * 10.0
            if p.form < 2.5:
                urgency += (2.5 - p.form) * 8.0
            return urgency

        out_candidates = sorted(analyzed_players, key=calculate_out_urgency, reverse=True)
        recommendations: List[TransferRecommendation] = []
        
        for candidate in out_candidates:
            if len(recommendations) >= max_recommendations:
                break
            
            reasons_out = []
            if candidate.status != "Available":
                reasons_out.append(f"Fitness Flag ({candidate.status})")
            if candidate.fixtures and candidate.fixtures[0].difficulty >= 4:
                reasons_out.append(f"Tough Match vs {candidate.fixtures[0].opponent_short_name} (FDR {candidate.fixtures[0].difficulty})")
            if candidate.form < 3.0:
                reasons_out.append(f"Cold Form ({candidate.form:.1f})")
            if candidate.score_breakdown.expected_points < 3.5:
                reasons_out.append(f"Low xP ({candidate.score_breakdown.expected_points:.2f})")
            
            if not reasons_out:
                reasons_out.append(f"Upgrade opportunity ({candidate.score_breakdown.expected_points:.2f} xP)")

            out_reason_str = " | ".join(reasons_out)
            available_budget = round(candidate.cost_m + bank_m, 1)
            
            current_club_counts: Dict[int, int] = {}
            for p in analyzed_players:
                if p.element != candidate.element:
                    current_club_counts[p.team_id] = current_club_counts.get(p.team_id, 0) + 1

            viable_targets = []
            for elem in all_elements:
                elem_id = elem["id"]
                elem_type = elem.get("element_type", 1)
                cost = round(float(elem.get("now_cost", 0)) / 10.0, 1)
                team_id = elem.get("team", 0)
                raw_status = elem.get("status", "a")

                if elem_id in squad_element_ids:
                    continue
                if elem_type != candidate.element_type:
                    continue
                if cost > available_budget:
                    continue
                if current_club_counts.get(team_id, 0) >= 3:
                    continue
                if raw_status not in ["a", "d"]:
                    continue

                p_fixtures = self.resolve_player_fixtures(team_id, target_gw, fixtures, teams_map)
                p_score = self.calculate_player_score(elem, p_fixtures)
                
                xp_gain = p_score.expected_points - candidate.score_breakdown.expected_points
                if xp_gain >= 0.4:
                    viable_targets.append((elem, p_fixtures, p_score, xp_gain, cost))

            if not viable_targets:
                continue

            viable_targets.sort(key=lambda x: x[3], reverse=True)
            best_elem, best_fix, best_score, best_xp_gain, in_cost = viable_targets[0]

            team_obj = teams_map.get(best_elem.get("team", 0), {})
            pos_obj = positions_map.get(best_elem.get("element_type", 1), {})
            
            raw_st = best_elem.get("status", "a")
            chance = best_elem.get("chance_of_playing_next_round")
            st_str = "Available" if raw_st == "a" else (f"Doubtful ({chance}%)" if raw_st == "d" and chance else raw_st)

            player_in_analysis = PlayerAnalysis(
                element=best_elem["id"],
                web_name=best_elem.get("web_name", "Unknown"),
                first_name=best_elem.get("first_name", ""),
                second_name=best_elem.get("second_name", ""),
                team_id=best_elem.get("team", 0),
                team_name=team_obj.get("name", "Unknown"),
                team_short_name=team_obj.get("short_name", "UNK"),
                element_type=best_elem.get("element_type", 1),
                position=pos_obj.get("singular_name_short", "UNK"),
                cost_m=in_cost,
                total_points=int(best_elem.get("total_points", 0)),
                form=float(best_elem.get("form", 0.0) or 0.0),
                expected_goals=float(best_elem.get("expected_goals", 0.0) or 0.0),
                expected_assists=float(best_elem.get("expected_assists", 0.0) or 0.0),
                expected_goal_involvements=float(best_elem.get("expected_goal_involvements", 0.0) or 0.0),
                status=st_str,
                chance_of_playing_next_round=chance,
                news=best_elem.get("news"),
                fixtures=best_fix,
                score_breakdown=best_score,
                recommended_role="Transfer IN Target"
            )

            cost_diff = round(in_cost - candidate.cost_m, 1)
            rem_bank = round(bank_m - cost_diff, 1)

            in_fix_str = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'} - FDR {f.difficulty})" for f in best_fix])
            in_reasons = [
                f"+{best_xp_gain:.2f} xP Gain ({best_score.expected_points:.2f} vs {candidate.score_breakdown.expected_points:.2f})",
                f"Form: {player_in_analysis.form:.1f}",
                f"Match: vs {in_fix_str}",
            ]
            if cost_diff < 0:
                in_reasons.append(f"Saves £{abs(cost_diff):.1f}m")
            elif cost_diff == 0:
                in_reasons.append("Exact budget")
            else:
                in_reasons.append(f"Costs +£{cost_diff:.1f}m (Bank: £{rem_bank:.1f}m)")

            in_reason_str = " | ".join(in_reasons)

            recommendations.append(
                TransferRecommendation(
                    player_out=candidate,
                    out_reason=out_reason_str,
                    player_in=player_in_analysis,
                    in_reason=in_reason_str,
                    expected_points_gain=round(best_xp_gain, 2),
                    cost_difference_m=cost_diff,
                    remaining_bank_m=rem_bank
                )
            )

        return recommendations

    def optimize_squad(
        self, 
        analyzed_players: List[PlayerAnalysis],
        all_elements: Optional[List[Dict[str, Any]]] = None,
        teams_map: Optional[Dict[int, Dict[str, Any]]] = None,
        positions_map: Optional[Dict[int, Dict[str, Any]]] = None,
        fixtures: Optional[List[Dict[str, Any]]] = None,
        target_gw: int = 1,
        bank_m: float = 0.0
    ) -> SquadOptimization:
        """
        Determine optimal Starting XI (1 GKP + 10 Outfield conforming to valid FPL formations),
        the strict Bench hierarchy (Sub 1-3 sorted by xP + Bench GK), Top 3 Captaincy Hierarchy,
        and algorithmic Transfer In / Out recommendations.
        """
        gkps = [p for p in analyzed_players if p.element_type == 1]
        defs = [p for p in analyzed_players if p.element_type == 2]
        mids = [p for p in analyzed_players if p.element_type == 3]
        fwds = [p for p in analyzed_players if p.element_type == 4]

        gkps.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)
        defs.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)
        mids.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)
        fwds.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)

        best_gkp = gkps[0] if gkps else analyzed_players[0]
        backup_gkp = gkps[1] if len(gkps) > 1 else None

        valid_formations = [
            (3, 5, 2), (3, 4, 3), (4, 4, 2), (4, 3, 3),
            (4, 5, 1), (5, 3, 2), (5, 4, 1), (5, 2, 3)
        ]

        best_formation_str = "3-4-3"
        best_starters: List[PlayerAnalysis] = []
        max_total_xp = -1.0

        for n_def, n_mid, n_fwd in valid_formations:
            if len(defs) >= n_def and len(mids) >= n_mid and len(fwds) >= n_fwd:
                selected = [best_gkp] + defs[:n_def] + mids[:n_mid] + fwds[:n_fwd]
                total_xp = sum(p.score_breakdown.expected_points for p in selected)
                if total_xp > max_total_xp:
                    max_total_xp = total_xp
                    best_formation_str = f"{n_def}-{n_mid}-{n_fwd}"
                    best_starters = selected

        if not best_starters:
            best_starters = analyzed_players[:11]

        # Remaining outfield players go to bench
        bench_outfield = [p for p in analyzed_players if p not in best_starters and p != backup_gkp]
        bench_outfield.sort(key=lambda x: x.score_breakdown.expected_points, reverse=True)

        best_bench: List[PlayerAnalysis] = bench_outfield.copy()
        if backup_gkp:
            best_bench.append(backup_gkp)

        for p in best_starters:
            p.is_recommended_starter = True
            p.recommended_role = "Starting XI"

        for idx, p in enumerate(best_bench):
            p.is_recommended_starter = False
            if p.element_type == 1:
                p.recommended_role = "Bench GK"
            else:
                p.recommended_role = f"Sub {idx + 1}"

        # Build Top 3 Captaincy Hierarchy
        captain_hierarchy = self.generate_captain_hierarchy(best_starters)
        recommended_cap = captain_hierarchy[0].player
        recommended_vc = captain_hierarchy[1].player if len(captain_hierarchy) > 1 else recommended_cap

        recommended_cap.is_recommended_captain = True
        recommended_vc.is_recommended_vice_captain = True

        differential_cap = captain_hierarchy[2].player if len(captain_hierarchy) > 2 else None

        # 1. Starting Lineup Promotions / Demotions
        lineup_changes: List[str] = []
        for p in best_starters:
            if not p.is_current_starter:
                opp_txt = p.fixtures[0].opponent_short_name if p.fixtures else "UNK"
                lineup_changes.append(
                    f"⭐ PROMOTED to Starting XI: {p.web_name} ({p.team_short_name} - {p.position}) was on Bench (#{p.squad_position}) -> Now Starting (Projected: {p.score_breakdown.expected_points:.2f} xP vs {opp_txt})."
                )

        for p in best_bench:
            if p.is_current_starter:
                lineup_changes.append(
                    f"🪑 DEMOTED to Bench: {p.web_name} ({p.team_short_name} - {p.position}) was in Starting XI (#{p.squad_position}) -> Benched (Projected: {p.score_breakdown.expected_points:.2f} xP, Status: {p.status})."
                )

        # 2. Bench Comparison & Tactical Sub Role Analysis
        bench_comparison: List[BenchComparisonItem] = []
        bench_adjustments: List[str] = []
        n_def_starters = len([p for p in best_starters if p.element_type == 2])

        for p in best_bench:
            if p.is_current_starter:
                cur_label = f"Current Starter (#{p.squad_position})"
            elif p.squad_position == 12:
                cur_label = "Current Bench GK (#12)"
            elif p.squad_position == 13:
                cur_label = "Current Sub 1 (#13)"
            elif p.squad_position == 14:
                cur_label = "Current Sub 2 (#14)"
            elif p.squad_position == 15:
                cur_label = "Current Sub 3 (#15)"
            else:
                cur_label = f"Current Bench (#{p.squad_position})"

            rec_label = p.recommended_role
            is_changed = (cur_label != f"Current {rec_label} (#{p.squad_position})")

            if p.element_type == 1:
                tac_tag = "🧤 GK Cover (Only plays if Starting GK misses out)"
            elif rec_label == "Sub 1":
                tac_tag = "⚡ Primary Auto-Sub (1st priority for ANY missing outfield starter)"
            elif n_def_starters == 3 and p.element_type == 2:
                tac_tag = "🛡️ Formation Lock DEF (Mandatory sub if any starting DEF is rested)"
            else:
                tac_tag = f"📋 Standard {rec_label} Cover (Enters if starters/earlier subs miss out)"

            opp_str = p.fixtures[0].opponent_short_name if p.fixtures else "UNK"
            fdr_str = str(p.fixtures[0].difficulty) if p.fixtures else "3"
            rat = f"{p.score_breakdown.expected_points:.2f} xP | Form: {p.form:.1f} vs {opp_str} (FDR {fdr_str})"

            bench_comparison.append(
                BenchComparisonItem(
                    player=p,
                    current_role=cur_label,
                    recommended_role=rec_label,
                    is_order_changed=is_changed,
                    tactical_tag=tac_tag,
                    rationale=rat
                )
            )

        # 3. Detect Outfield Sub Priority Mismatches
        outfield_bench_recommended = [p for p in best_bench if p.element_type != 1]
        outfield_bench_current = sorted(
            [p for p in analyzed_players if p.squad_position in [13, 14, 15]],
            key=lambda x: x.squad_position
        )

        for idx, rec_p in enumerate(outfield_bench_recommended):
            rec_sub_num = idx + 1
            if idx < len(outfield_bench_current):
                cur_p = outfield_bench_current[idx]
                if rec_p.element != cur_p.element and not rec_p.is_current_starter:
                    bench_adjustments.append(
                        f"🔄 SUB ORDER SWAP: Move {rec_p.web_name} ({rec_p.score_breakdown.expected_points:.2f} xP) to Sub {rec_sub_num} (currently Sub {cur_p.squad_position - 12} has {cur_p.web_name} with {cur_p.score_breakdown.expected_points:.2f} xP)."
                    )

        # Risk warnings
        warnings: List[str] = []
        for p in best_starters:
            if p.status != "Available":
                warnings.append(f"⚠️ Starter '{p.web_name}' has an injury/doubt flag ({p.status} - {p.score_breakdown.availability_rate * 100:.0f}% chance).")
            if p.fixtures and p.fixtures[0].difficulty >= 5:
                warnings.append(f"⚡ Starter '{p.web_name}' faces maximum difficulty FDR 5 match ({p.fixtures[0].opponent_name}).")

        if best_bench and best_bench[0].element_type != 1 and best_starters:
            lowest_starter_xp = min(p.score_breakdown.expected_points for p in best_starters if p.element_type != 1)
            if best_bench[0].score_breakdown.expected_points > lowest_starter_xp:
                warnings.append(f"💡 Bench Dilemma: Sub 1 '{best_bench[0].web_name}' ({best_bench[0].score_breakdown.expected_points} xP) is narrowly left out due to formation constraints.")

        # Generate Transfer Recommendations if catalog provided
        transfer_recs = []
        if all_elements and teams_map and positions_map and fixtures:
            transfer_recs = self.generate_transfer_recommendations(
                analyzed_players, all_elements, teams_map, positions_map, fixtures, target_gw, bank_m
            )

        return SquadOptimization(
            formation=best_formation_str,
            recommended_starting_xi=best_starters,
            recommended_bench=best_bench,
            captain_hierarchy=captain_hierarchy,
            recommended_captain=recommended_cap,
            recommended_vice_captain=recommended_vc,
            differential_captain=differential_cap,
            transfer_recommendations=transfer_recs,
            bench_comparison=bench_comparison,
            bench_adjustments=list(dict.fromkeys(bench_adjustments)),
            lineup_changes=lineup_changes,
            total_projected_xp=round(max_total_xp, 2),
            risk_warnings=warnings
        )


    def analyze_manager_squad(
        self, 
        manager_id: int, 
        gw: Optional[int] = None,
        fpl_cookie: Optional[str] = None,
        transfers_in: Optional[List[int]] = None,
        transfers_out: Optional[List[int]] = None,
    ) -> ManagerSquadAnalysisReport:
        """
        Run full automated analysis on a manager's squad for the target Gameweek.
        Supports pre-deadline saved transfers via authenticated cookie or explicit transfer overrides.
        """
        # 1. Fetch bootstrap data
        bootstrap = self.client.get_bootstrap_static()
        elements_map = {e["id"]: e for e in bootstrap.get("elements", [])}
        teams_map = {t["id"]: t for t in bootstrap.get("teams", [])}
        positions_map = {et["id"]: et for et in bootstrap.get("element_types", [])}

        # 2. Determine target Gameweek & Manager metadata
        upcoming_gw, deadline = self.get_upcoming_gameweek(bootstrap)
        
        # Enforce that only upcoming/future Gameweeks (>= upcoming_gw) are analyzed
        if gw is not None:
            if gw < upcoming_gw:
                target_gw = upcoming_gw
            else:
                target_gw = min(gw, 38)
        else:
            target_gw = upcoming_gw

        manager_profile = self.client.get_manager(manager_id)
        manager_name = f"{manager_profile.get('player_first_name', '')} {manager_profile.get('player_last_name', '')}".strip()
        team_name = manager_profile.get("name", "")

        # 3. Fetch all fixtures for target GW
        fixtures = self.client.get_fixtures(event_id=target_gw)

        # 4. Fetch manager squad picks
        # Strategy A: Check authenticated /my-team/ endpoint if cookie provided or in config
        picks = []
        bank_m = 0.0

        cookie_to_use = fpl_cookie
        from src.config import FPLConfig
        if not cookie_to_use:
            cookie_to_use = FPLConfig.FPL_COOKIE

        if cookie_to_use:
            try:
                my_team_data = self.client.get_my_team(manager_id, cookie=cookie_to_use)
                if isinstance(my_team_data, dict) and "picks" in my_team_data:
                    picks = my_team_data["picks"]
                    trans_info = my_team_data.get("transfers", {})
                    bank_raw = trans_info.get("bank", 0)
                    bank_m = round(float(bank_raw) / 10.0, 1)
            except Exception:
                picks = []

        # Strategy B: Public API fallback (latest active gameweek squad)
        if not picks:
            current_event = manager_profile.get("current_event") or 1
            squad_gw = target_gw if target_gw <= current_event else current_event
            try:
                picks_data = self.client.get_manager_picks(manager_id, squad_gw)
            except Exception:
                picks_data = self.client.get_manager_picks(manager_id, current_event)

            picks = picks_data.get("picks", [])
            entry_hist = picks_data.get("entry_history", {})
            bank_m = round(float(entry_hist.get("bank", 0)) / 10.0, 1) if entry_hist else 0.0

        # Strategy C: Apply manual transfer overrides if requested
        if transfers_in and transfers_out:
            updated_picks = []
            out_queue = list(transfers_out)
            in_queue = list(transfers_in)

            for pick in picks:
                elem_id = pick.get("element")
                if elem_id in out_queue and in_queue:
                    out_elem = elem_id
                    new_elem = in_queue.pop(0)
                    out_queue.remove(out_elem)

                    old_cost = round(float(elements_map.get(out_elem, {}).get("now_cost", 0)) / 10.0, 1)
                    new_cost = round(float(elements_map.get(new_elem, {}).get("now_cost", 0)) / 10.0, 1)
                    bank_m = round(bank_m + old_cost - new_cost, 1)

                    new_pick = pick.copy()
                    new_pick["element"] = new_elem
                    updated_picks.append(new_pick)
                else:
                    updated_picks.append(pick)
            picks = updated_picks

        # 5. Build and score each player
        analyzed_players: List[PlayerAnalysis] = []
        for pick in picks:
            elem_id = pick.get("element")
            pos_num = pick.get("position", 1)
            is_cap = bool(pick.get("is_captain", False))
            is_vc = bool(pick.get("is_vice_captain", False))

            elem = elements_map.get(elem_id, {})
            team_id = elem.get("team", 0)
            team_obj = teams_map.get(team_id, {})
            elem_type_id = elem.get("element_type", 1)
            pos_obj = positions_map.get(elem_type_id, {})

            # Resolve fixture(s) for target GW
            player_fixtures = self.resolve_player_fixtures(team_id, target_gw, fixtures, teams_map)

            # Calculate score & xP
            score_breakdown = self.calculate_player_score(elem, player_fixtures)

            raw_status = elem.get("status", "a")
            chance = elem.get("chance_of_playing_next_round")
            status_str = "Available" if raw_status == "a" else (f"Doubtful ({chance}%)" if raw_status == "d" and chance else raw_status)

            player_analysis = PlayerAnalysis(
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
                is_current_captain=is_cap,
                is_current_vice_captain=is_vc,
                fixtures=player_fixtures,
                score_breakdown=score_breakdown
            )
            analyzed_players.append(player_analysis)

        # 6. Optimize Lineup, Bench, Captaincy & Transfers
        optimization = self.optimize_squad(
            analyzed_players=analyzed_players,
            all_elements=bootstrap.get("elements", []),
            teams_map=teams_map,
            positions_map=positions_map,
            fixtures=fixtures,
            target_gw=target_gw,
            bank_m=bank_m
        )

        return ManagerSquadAnalysisReport(
            manager_id=manager_id,
            manager_name=manager_name,
            team_name=team_name,
            target_gameweek=target_gw,
            next_deadline=deadline,
            players=analyzed_players,
            optimization=optimization
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
        Export squad analysis as a clean, tabular Pandas DataFrame.
        """
        report = self.analyze_manager_squad(
            manager_id=manager_id, 
            gw=gw, 
            fpl_cookie=fpl_cookie, 
            transfers_in=transfers_in, 
            transfers_out=transfers_out
        )
        rows = []

        for p in report.players:
            fix_str = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'} - FDR {f.difficulty})" for f in p.fixtures])
            rec_role = p.recommended_role
            if p.is_recommended_captain:
                rec_role += " (C)"
            elif p.is_recommended_vice_captain:
                rec_role += " (VC)"

            rows.append({
                "Player": p.web_name,
                "Team": p.team_short_name,
                "Pos": p.position,
                "Cost": f"£{p.cost_m:.1f}m",
                "Opponent (FDR)": fix_str,
                "Form": p.form,
                "xG": p.expected_goals,
                "xA": p.expected_assists,
                "xP": p.score_breakdown.expected_points,
                "Score (0-100)": p.score_breakdown.composite_score,
                "Recommended Role": rec_role,
                "Status": p.status,
                "Tags": ", ".join(p.score_breakdown.tags[:2]) if p.score_breakdown.tags else ""
            })

        df = pd.DataFrame(rows)
        # Sort by xP descending
        df = df.sort_values(by="xP", ascending=False)
        return df
