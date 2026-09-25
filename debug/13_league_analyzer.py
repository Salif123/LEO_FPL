"""
Debug Script: Mini-League Rival Tracker & Effective Ownership (EO) Engine
Analyzes mini-league standings, squad similarity / overlap % against rivals,
captaincy distribution, and calculates player Effective Ownership (EO).

Run:
    python debug/13_league_analyzer.py [league_id] [manager_id]
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient
from src.analysis.league_analyzer import LeagueAnalyzer


def main():
    client = FPLClient()

    league_id = 314  # Default sample classic league ID
    manager_id = None

    if len(sys.argv) > 1:
        try:
            league_id = int(sys.argv[1])
        except ValueError:
            league_id = 314
    else:
        print("=" * 80)
        print("🏆  MINI-LEAGUE RIVAL TRACKER & EFFECTIVE OWNERSHIP (EO) ENGINE")
        print("=" * 80)
        lid_raw = input("Enter Mini-League ID [Default: 314]: ").strip()
        league_id = int(lid_raw) if lid_raw else 314

        mid_raw = input("Enter Your Manager ID (optional, for head-to-head comparison): ").strip()
        manager_id = int(mid_raw) if mid_raw else None

    if len(sys.argv) > 2:
        try:
            manager_id = int(sys.argv[2])
        except ValueError:
            manager_id = None

    print(f"\nAnalyzing Mini-League #{league_id} (Target Manager: #{manager_id or 'None'})...")

    try:
        analyzer = LeagueAnalyzer(client)
        report = analyzer.analyze_mini_league(league_id, target_manager_id=manager_id)

        print("\n" + "=" * 85)
        print(f"  🏆 LEAGUE NAME   : {report.league_name} (ID: {report.league_id})")
        print(f"  👥 TOTAL MANAGERS: {report.total_managers} Managers")
        print(f"  🎯 GAMEWEEK      : GW {report.target_gameweek}")
        print("=" * 85)

        # 1. Captaincy Consensus Distribution
        print("\n👑 CAPTAINCY DISTRIBUTION IN THIS LEAGUE:")
        print("-" * 85)
        for cap_name, pct in report.top_captains_distribution.items():
            bar = "█" * int(pct / 5)
            print(f"  • {cap_name:<20} : {pct:>5.1f}% {bar}")

        # 2. Top Effective Ownership (EO) Table
        print("\n📊 TOP 15 EFFECTIVE OWNERSHIP (EO) PLAYERS IN THIS LEAGUE:")
        print("-" * 85)
        eo_df = analyzer.get_league_eo_df(league_id, target_manager_id=manager_id)
        if not eo_df.empty:
            print(eo_df.head(15).to_string(index=False))

        # 3. Head-to-Head Rival Comparison
        if manager_id and report.rival_comparisons:
            print("\n⚔️ HEAD-TO-HEAD SQUAD OVERLAP VS RIVALS:")
            print("-" * 85)
            rival_df = analyzer.get_rival_overlap_df(league_id, target_manager_id=manager_id)
            if not rival_df.empty:
                print(rival_df.to_string(index=False))

        # 4. Tactical Summary
        if report.tactical_summary:
            print("\n💡 TACTICAL LEAGUE INSIGHTS:")
            print("-" * 85)
            for tip in report.tactical_summary:
                print(f"  • {tip}")

    except Exception as e:
        print(f"\n[ERROR] Mini-league analysis failed: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
