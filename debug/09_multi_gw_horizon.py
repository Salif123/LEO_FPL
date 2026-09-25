"""
Debug Script: Multi-Gameweek Horizon Engine & Fixture Swings
Evaluates squad performance across a multi-GW horizon (e.g. 3 to 8 Gameweeks),
detects fixture swings across Premier League clubs, and projects GW-by-GW optimal lineups.

Run:
    python debug/09_multi_gw_horizon.py [manager_id] [horizon_length] [start_gw]
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient
from src.analysis.multi_gw_analyzer import MultiGWAnalyzer


def main():
    client = FPLClient()
    bootstrap = client.get_bootstrap_static()
    analyzer = MultiGWAnalyzer(client)
    upcoming_gw, deadline = analyzer.get_upcoming_gameweek(bootstrap)

    # Parse CLI arguments
    manager_id = 1
    horizon_length = 5
    start_gw = upcoming_gw

    if len(sys.argv) > 1:
        try:
            manager_id = int(sys.argv[1])
        except ValueError:
            manager_id = 1
    else:
        print("=" * 80)
        print("🔭  MULTI-GAMEWEEK HORIZON ENGINE & FIXTURE RUN ANALYTICS")
        print("=" * 80)
        print(f"📌 Upcoming Gameweek: GW {upcoming_gw}" + (f" (Deadline: {deadline})" if deadline else ""))
        mid_raw = input("Enter Manager ID [Default: 1]: ").strip()
        manager_id = int(mid_raw) if mid_raw else 1
        
        hlen_raw = input("Enter Horizon Length in Gameweeks (1-8) [Default: 5]: ").strip()
        horizon_length = int(hlen_raw) if hlen_raw else 5

        sgw_raw = input(f"Enter Starting Gameweek [{upcoming_gw}-38] [Default: {upcoming_gw}]: ").strip()
        start_gw = int(sgw_raw) if sgw_raw else upcoming_gw

    if len(sys.argv) > 2:
        try:
            horizon_length = int(sys.argv[2])
        except ValueError:
            horizon_length = 5

    if len(sys.argv) > 3:
        try:
            start_gw = int(sys.argv[3])
        except ValueError:
            start_gw = upcoming_gw

    print(f"\nAnalyzing Multi-GW Horizon (GW {start_gw} to {min(38, start_gw + horizon_length - 1)}) for Manager ID: {manager_id}...")

    try:
        report = client.analyze_manager_horizon(
            manager_id=manager_id,
            horizon_length=horizon_length,
            start_gw=start_gw
        )

        print("\n" + "=" * 85)
        print(f"  👤 MANAGER   : {report.manager_name} | TEAM: {report.team_name}")
        print(f"  📅 WINDOW    : GW {report.start_gameweek} to GW {report.end_gameweek} ({report.horizon_length} Gameweeks)")
        print(f"  📈 TOTAL xP  : {report.total_horizon_xp:.1f} pts (Average: {report.avg_xp_per_gw:.1f} pts/GW)")
        print("=" * 85)

        # 1. Gameweek-by-Gameweek Lineup & Captaincy Projections
        print("\n🗓️ GAMEWEEK-BY-GAMEWEEK SQUAD PROJECTIONS:")
        print("-" * 85)
        for gw_proj in report.gameweek_squads:
            cap = gw_proj.captain.player
            vc = gw_proj.vice_captain.player
            print(f"  • GW {gw_proj.gameweek} -> Projected: {gw_proj.projected_xp:.1f} xP | Formation: {gw_proj.formation} | (C): {cap.web_name} ({gw_proj.captain.expected_points:.1f} xP) | (VC): {vc.web_name}")

        # 2. Player-by-Player Horizon Projections Table
        print("\n📊 SQUAD PLAYER HORIZON MATRIX:")
        df = analyzer.get_horizon_summary_df(manager_id, horizon_length, start_gw)
        print(df.to_string(index=False))

        # 3. League-Wide Fixture Swings
        print("\n🔄 LEAGUE-WIDE FIXTURE SWINGS (GW " + f"{report.start_gameweek}-{report.end_gameweek}):")
        print("-" * 85)
        print(f"{'Club':<22} | {'FDR Sequence':<18} | {'Avg FDR':<8} | {'Sentiment':<18} | {'Key Assets'}")
        print("-" * 85)
        for swing in report.fixture_swings:
            fdr_seq_str = "-".join(map(str, swing.fdr_sequence))
            assets_str = ", ".join(swing.key_assets[:2])
            print(f"{swing.team_name:<22} | {fdr_seq_str:<18} | {swing.fdr_avg:<8.2f} | {swing.sentiment:<18} | {assets_str}")

        # 4. Strategic Warnings
        if report.strategic_warnings:
            print("\n🚨 STRATEGIC HORIZON ALERTS:")
            for w in report.strategic_warnings:
                print(f"  • {w}")

    except Exception as e:
        print(f"\n[ERROR] Multi-GW analysis failed: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
