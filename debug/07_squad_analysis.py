"""
Debug Script: FPL Manager Squad Analysis & Predictive Player Scoring
Run via UV or Python:
    python debug/07_squad_analysis.py
    python debug/07_squad_analysis.py [manager_id] [gw]
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient


def main():
    client = FPLClient()
    bootstrap = client.get_bootstrap_static()
    from src.analysis.squad_analyzer import SquadAnalyzer
    analyzer = SquadAnalyzer(client)
    upcoming_gw, deadline = analyzer.get_upcoming_gameweek(bootstrap)

    if len(sys.argv) > 1:
        try:
            manager_id = int(sys.argv[1])
        except ValueError:
            manager_id = 1
        
        gw = None
        if len(sys.argv) > 2:
            try:
                cli_gw = int(sys.argv[2])
                if cli_gw < upcoming_gw:
                    print(f"⚠️  GW {cli_gw} is in the past. Automatically using upcoming GW {upcoming_gw}.")
                    gw = upcoming_gw
                else:
                    gw = min(cli_gw, 38)
            except ValueError:
                gw = upcoming_gw
        else:
            gw = upcoming_gw
    else:
        print("=" * 70)
        print("🧠  FPL SQUAD ANALYSIS & PREDICTIVE SCORING ENGINE")
        print("=" * 70)
        print(f"📌 Upcoming Gameweek: GW {upcoming_gw}" + (f" (Deadline: {deadline})" if deadline else ""))
        print("=" * 70)
        mid_raw = input("Enter Manager ID [Default: 1]: ").strip()
        manager_id = int(mid_raw) if mid_raw else 1
        
        gw_prompt = f"Enter Upcoming Gameweek [{upcoming_gw}-38] [Default: {upcoming_gw}]: "
        gw_raw = input(gw_prompt).strip()
        
        if gw_raw:
            try:
                chosen_gw = int(gw_raw)
                if chosen_gw < upcoming_gw:
                    print(f"⚠️  GW {chosen_gw} is in the past (already finished). Automatically using upcoming GW {upcoming_gw}.")
                    gw = upcoming_gw
                elif chosen_gw > 38:
                    print(f"⚠️  GW {chosen_gw} exceeds 38. Using GW 38.")
                    gw = 38
                else:
                    gw = chosen_gw
            except ValueError:
                gw = upcoming_gw
        else:
            gw = upcoming_gw
    print(f"\nAnalyzing squad for Manager ID: {manager_id}...")
    
    try:
        report = client.analyze_manager_squad(manager_id, gw)
        opt = report.optimization
        
        print("\n" + "=" * 80)
        print(f"  👤 MANAGER   : {report.manager_name} | TEAM: {report.team_name}")
        print(f"  🎯 GAMEWEEK  : GW {report.target_gameweek}" + (f" (Deadline: {report.next_deadline})" if report.next_deadline else ""))
        print(f"  📐 FORMATION : {opt.formation} | 📈 PROJECTED TOTAL xP: {opt.total_projected_xp:.1f} pts")
        print("=" * 80)

        # 1. Top 3 Captaincy Hierarchy
        print("\n👑 TOP 3 CAPTAINCY HIERARCHY:")
        print("-" * 80)
        for cap_choice in opt.captain_hierarchy:
            p = cap_choice.player
            fix_str = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'} - FDR {f.difficulty})" for f in p.fixtures])
            print(f"  #{cap_choice.rank} {cap_choice.role_name:<30} : {p.web_name} ({p.team_short_name} - {p.position})")
            print(f"     Match: vs {fix_str} | Projected: {cap_choice.expected_points:.2f} xP | Threat Index: {cap_choice.threat_index:.1f}/100")
            print(f"     Why: {cap_choice.rationale}")

        # 2. Recommended Starting XI (Positionally Grouped)
        print(f"\n⭐ RECOMMENDED STARTING XI ({opt.formation} Formation):")
        print(f"{'Role':<12} | {'Player':<18} | {'Club':<5} | {'Opponent (FDR)':<16} | {'Form':<5} | {'xG':<5} | {'xP':<5} | {'Score':<6} | {'Status'}")
        print("-" * 85)
        for p in opt.recommended_starting_xi:
            cap_badge = ""
            if p.is_recommended_captain:
                cap_badge = " (C)"
            elif p.is_recommended_vice_captain:
                cap_badge = " (VC)"
            
            fix_str = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'}-{f.difficulty})" for f in p.fixtures])
            pos_label = f"Starter ({p.position})"
            print(f"{pos_label:<12} | {p.web_name + cap_badge:<18} | {p.team_short_name:<5} | {fix_str:<16} | {p.form:<5.1f} | {p.expected_goals:<5.2f} | {p.score_breakdown.expected_points:<5.2f} | {p.score_breakdown.composite_score:<6.1f} | {p.status}")

        # 3. Recommended Bench Hierarchy & Tactical Auto-Sub Order
        print("\n🪑 RECOMMENDED BENCH HIERARCHY (PRIORITIZED SUB ORDER):")
        print(f"{'Priority':<12} | {'Player':<18} | {'Club':<5} | {'Pos':<4} | {'Opponent (FDR)':<16} | {'xP':<5} | {'Score':<6} | {'Status'}")
        print("-" * 85)
        for p in opt.recommended_bench:
            fix_str = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'}-{f.difficulty})" for f in p.fixtures])
            print(f"{p.recommended_role:<12} | {p.web_name:<18} | {p.team_short_name:<5} | {p.position:<4} | {fix_str:<16} | {p.score_breakdown.expected_points:<5.2f} | {p.score_breakdown.composite_score:<6.1f} | {p.status}")

        # 4. Tactical Bench Order & Lineup Promotions/Demotions
        if opt.lineup_changes or opt.bench_adjustments or opt.bench_comparison:
            print("\n🔄 BENCH OPTIMIZATION & AUTO-SUB STRATEGY:")
            print("-" * 85)
            if opt.lineup_changes:
                print("  Starting XI vs Bench Movements:")
                for lc in opt.lineup_changes:
                    print(f"    • {lc}")
            
            if opt.bench_adjustments:
                print("\n  Recommended Bench Slot Swaps:")
                for ba in opt.bench_adjustments:
                    print(f"    • {ba}")

            print("\n  Bench Player Auto-Sub Functions:")
            for b_item in opt.bench_comparison:
                p = b_item.player
                print(f"    • {p.web_name:<14} ({p.team_short_name} - {p.position}) [{p.score_breakdown.expected_points:.2f} xP] : {b_item.tactical_tag}")

        # 5. Metric-Driven Transfer Recommendations (Transfer In / Out)
        if opt.transfer_recommendations:
            print("\n🔄 METRIC-DRIVEN TRANSFER RECOMMENDATIONS:")
            print("-" * 85)
            for idx, tr in enumerate(opt.transfer_recommendations, 1):
                p_out = tr.player_out
                p_in = tr.player_in
                print(f"  Option {idx}:")
                print(f"    🔴 Transfer OUT : {p_out.web_name} ({p_out.team_short_name} - {p_out.position}) £{p_out.cost_m:.1f}m [{p_out.score_breakdown.expected_points:.2f} xP]")
                print(f"       Reason       : {tr.out_reason}")
                print(f"    🟢 Transfer IN  : {p_in.web_name} ({p_in.team_short_name} - {p_in.position}) £{p_in.cost_m:.1f}m [{p_in.score_breakdown.expected_points:.2f} xP]")
                print(f"       Reason       : {tr.in_reason}")
                print(f"       Net Impact   : 📈 +{tr.expected_points_gain:.2f} xP Gain | Bank Balance: £{tr.remaining_bank_m:.1f}m\n")

        # 6. Warnings & Tactical Notes
        if opt.risk_warnings:
            print("🚨 RISK WARNINGS & TACTICAL NOTES:")
            for w in opt.risk_warnings:
                print(f"  • {w}")

        # 7. Full Tabular View
        print("\n" + "=" * 85)
        print("📊 COMPLETE SQUAD RANKING (SORTED BY xP):")
        print("=" * 85)
        df = client.get_squad_analysis_df(manager_id, gw)
        print(df[["Player", "Team", "Pos", "Opponent (FDR)", "Form", "xP", "Score (0-100)", "Recommended Role", "Status"]].to_string(index=False))

    except Exception as e:
        print(f"\n[ERROR] Analysis failed: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
