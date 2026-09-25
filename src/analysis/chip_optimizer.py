"""
Chip Strategy & Valuation Engine for FPL.
Analyzes optimal timing for Wildcard (WC), Free Hit (FH), Bench Boost (BB),
and Triple Captain (TC) based on fixture anomalies (DGW/BGW), squad health, and bench xP.
"""
from typing import Any, Dict, List, Optional, Tuple

from src.models.analysis import ChipStrategyRoadmap, ChipValuation, PlayerAnalysis


class ChipOptimizer:
    """FPL seasonal chip strategy and valuation engine."""

    def __init__(self, fpl_client: Any):
        """
        :param fpl_client: An instance of FPLClient
        """
        self.client = fpl_client

    def evaluate_chips(
        self,
        manager_id: int,
        target_gw: Optional[int] = None,
        fpl_cookie: Optional[str] = None,
        use_cache: bool = True
    ) -> ChipStrategyRoadmap:
        """
        Evaluate chip status and identify optimal upcoming gameweek windows for each available chip.
        """
        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer = SquadAnalyzer(self.client)

        bootstrap = self.client.get_bootstrap_static(use_cache=use_cache)
        events = bootstrap.get("events", [])
        upcoming_gw, _ = analyzer.get_upcoming_gameweek(bootstrap)
        s_gw = target_gw if (target_gw is not None and target_gw >= upcoming_gw) else upcoming_gw

        all_fixtures = self.client.get_fixtures(event_id=None, use_cache=use_cache)

        # 1. Fetch Manager History to identify chips already used
        history_data = self.client.get_manager_history(manager_id, use_cache=use_cache)
        chips_used_list = history_data.get("chips", [])
        chips_used: Dict[str, int] = {}
        for c in chips_used_list:
            chips_used[c.get("name", "")] = c.get("event", 0)

        all_chips = ["wildcard", "freehit", "bboost", "3xc"]
        chips_remaining = [c for c in all_chips if c not in chips_used]

        # 2. Analyze Current Squad
        report = analyzer.analyze_manager_squad(
            manager_id=manager_id, gw=s_gw, fpl_cookie=fpl_cookie, use_cache=use_cache
        )
        squad_players = report.players

        recommendations: List[ChipValuation] = []
        calendar_summary: List[str] = []

        # ---------------------------------------------------------------------
        # A. Wildcard Evaluation
        # ---------------------------------------------------------------------
        if "wildcard" in chips_remaining:
            # Check squad health and upcoming difficulty
            flagged_count = len([p for p in squad_players if p.status != "Available"])
            low_xp_count = len([p for p in squad_players if p.score_breakdown.expected_points < 3.0])
            
            if flagged_count >= 3 or low_xp_count >= 5:
                wc_rec_gw = s_gw
                wc_upside = round((flagged_count * 3.5) + (low_xp_count * 2.0), 1)
                wc_conf = 88.0
                wc_reason = f"Immediate Emergency Wildcard Recommended: Squad has {flagged_count} injured/doubtful players and {low_xp_count} underperforming assets."
            else:
                # Suggest optimal fixture swing window (e.g. GW 12 or GW 28-31)
                wc_rec_gw = min(38, s_gw + 4)
                wc_upside = 18.5
                wc_conf = 72.0
                wc_reason = f"Hold Wildcard until major fixture swing window around GW {wc_rec_gw} to target fresh club runs."

            recommendations.append(
                ChipValuation(
                    chip_name="wildcard",
                    recommended_gw=wc_rec_gw,
                    projected_upside_xp=wc_upside,
                    confidence_score=wc_conf,
                    trigger_reason=wc_reason,
                    alternative_gws=[wc_rec_gw + 1, wc_rec_gw + 2]
                )
            )
            calendar_summary.append(f"🃏 Wildcard: Optimal around GW {wc_rec_gw} ({wc_reason})")

        # ---------------------------------------------------------------------
        # B. Free Hit Evaluation (Blank / Double Gameweek Search)
        # ---------------------------------------------------------------------
        if "freehit" in chips_remaining:
            # Scan upcoming gameweeks for Blank or Double fixtures
            gw_fixture_counts: Dict[int, int] = {}
            for f in all_fixtures:
                ev = f.get("event")
                if ev and ev >= s_gw:
                    gw_fixture_counts[ev] = gw_fixture_counts.get(ev, 0) + 1

            # Normal GW has 10 fixtures. BGW < 10, DGW > 10
            anomalous_gws = [gw for gw, count in gw_fixture_counts.items() if count != 10]
            if anomalous_gws:
                best_fh_gw = anomalous_gws[0]
                fh_type = "Blank Gameweek (few fixtures)" if gw_fixture_counts[best_fh_gw] < 10 else "Double Gameweek (bonus fixtures)"
                fh_upside = 24.0
                fh_conf = 92.0
                fh_reason = f"Save for {fh_type} in GW {best_fh_gw} (only {gw_fixture_counts[best_fh_gw]} matches) to field a full premium XI."
            else:
                best_fh_gw = min(38, max(s_gw + 6, 29))
                fh_upside = 15.0
                fh_conf = 65.0
                fh_reason = f"Hold for spring Blank/Double Gameweek announcements (typically GW 29 or GW 34)."

            recommendations.append(
                ChipValuation(
                    chip_name="freehit",
                    recommended_gw=best_fh_gw,
                    projected_upside_xp=fh_upside,
                    confidence_score=fh_conf,
                    trigger_reason=fh_reason,
                    alternative_gws=[best_fh_gw + 1] if best_fh_gw < 38 else []
                )
            )
            calendar_summary.append(f"🆓 Free Hit: Target GW {best_fh_gw} ({fh_reason})")

        # ---------------------------------------------------------------------
        # C. Bench Boost Evaluation
        # ---------------------------------------------------------------------
        if "bboost" in chips_remaining:
            bench_players = [p for p in squad_players if p.squad_position > 11]
            bench_xp_now = sum(p.score_breakdown.expected_points for p in bench_players)
            
            if bench_xp_now >= 16.0:
                bb_gw = s_gw
                bb_upside = round(bench_xp_now, 1)
                bb_conf = 85.0
                bb_reason = f"High Bench Potential in GW {s_gw}: Current bench is projected for {bench_xp_now:.1f} xP with favorable fixtures."
            else:
                bb_gw = min(38, max(s_gw + 8, 34))
                bb_upside = 20.0
                bb_conf = 78.0
                bb_reason = "Pair with a Double Gameweek (typically GW 34 or 37) immediately after a Wildcard to ensure 15 starting double-gameweek players."

            recommendations.append(
                ChipValuation(
                    chip_name="bboost",
                    recommended_gw=bb_gw,
                    projected_upside_xp=bb_upside,
                    confidence_score=bb_conf,
                    trigger_reason=bb_reason,
                    alternative_gws=[bb_gw + 1] if bb_gw < 38 else []
                )
            )
            calendar_summary.append(f"🚀 Bench Boost: Target GW {bb_gw} ({bb_reason})")

        # ---------------------------------------------------------------------
        # D. Triple Captain Evaluation
        # ---------------------------------------------------------------------
        if "3xc" in chips_remaining:
            # Find top captain choice in the squad
            starters = [p for p in squad_players if p.squad_position <= 11]
            top_cap = max(starters, key=lambda x: x.score_breakdown.expected_points) if starters else squad_players[0]

            if top_cap.score_breakdown.expected_points >= 10.0:
                tc_gw = s_gw
                tc_upside = round(top_cap.score_breakdown.expected_points, 1)
                tc_conf = 88.0
                tc_reason = f"Prime Triple Captaincy in GW {s_gw}: {top_cap.web_name} is in peak form with projected {top_cap.score_breakdown.expected_points:.1f} xP."
            else:
                tc_gw = min(38, max(s_gw + 5, 25))
                tc_upside = 14.0
                tc_conf = 80.0
                tc_reason = f"Hold Triple Captain for a Double Gameweek where a premium asset (e.g. Haaland/Salah) plays twice at home."

            recommendations.append(
                ChipValuation(
                    chip_name="3xc",
                    recommended_gw=tc_gw,
                    projected_upside_xp=tc_upside,
                    confidence_score=tc_conf,
                    trigger_reason=tc_reason,
                    alternative_gws=[tc_gw + 1] if tc_gw < 38 else []
                )
            )
            calendar_summary.append(f"👑 Triple Captain: Target GW {tc_gw} ({tc_reason})")

        return ChipStrategyRoadmap(
            manager_id=manager_id,
            chips_remaining=chips_remaining,
            chips_used=chips_used,
            recommendations=recommendations,
            optimal_calendar_summary=calendar_summary
        )
