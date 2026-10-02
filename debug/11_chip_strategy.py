"""
Debug Script: Seasonal Chip Strategy & Valuation Engine
Evaluates remaining chips (Wildcard, Free Hit, Bench Boost, Triple Captain)
and projects optimal execution windows based on fixture anomalies (DGW/BGW) and squad status.

Run:
    python debug/11_chip_strategy.py [manager_id]
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient
from src.analysis.chip_optimizer import ChipOptimizer


def main():
    client = FPLClient()
    bootstrap = client.get_bootstrap_static()
    from src.analysis.squad_analyzer import SquadAnalyzer
    analyzer = SquadAnalyzer(client)
    upcoming_gw, deadline = analyzer.get_upcoming_gameweek(bootstrap)

    manager_id = 1
    if len(sys.argv) > 1:
        try:
            manager_id = int(sys.argv[1])
        except ValueError:
            manager_id = 1
    else:
        print("=" * 80)
        print("🃏  SEASONAL CHIP STRATEGY & ROADMAP ENGINE")
        print("=" * 80)
        print(f"📌 Upcoming Gameweek: GW {upcoming_gw}" + (f" (Deadline: {deadline})" if deadline else ""))
        mid_raw = input("Enter Manager ID [Default: 1]: ").strip()
        manager_id = int(mid_raw) if mid_raw else 1

    print(f"\nEvaluating Chip Strategy for Manager #{manager_id}...")

    try:
        roadmap = client.evaluate_chips(manager_id=manager_id, target_gw=upcoming_gw)

        print("\n" + "=" * 85)
        print(f"  🎟️ CHIPS REMAINING : {', '.join(c.upper() for c in roadmap.chips_remaining) if roadmap.chips_remaining else 'None (All Chips Used)'}")
        if roadmap.chips_used:
            used_str = ", ".join([f"{k.upper()} (GW {v})" for k, v in roadmap.chips_used.items()])
            print(f"  📜 CHIPS USED      : {used_str}")
        print("=" * 85)

        print("\n🎯 CHIP EXECUTION ROADMAP & VALUATIONS:")
        print("-" * 85)
        for rec in roadmap.recommendations:
            chip_title = {
                "wildcard": "🃏 WILDCARD",
                "freehit": "🆓 FREE HIT",
                "bboost": "🚀 BENCH BOOST",
                "3xc": "👑 TRIPLE CAPTAIN"
            }.get(rec.chip_name, rec.chip_name.upper())

            alt_str = f" (Alternatives: GW {', '.join(map(str, rec.alternative_gws))})" if rec.alternative_gws else ""
            print(f"  {chip_title:<18} -> Recommended Target: GW {rec.recommended_gw}{alt_str}")
            print(f"     Projected Upside : +{rec.projected_upside_xp:.1f} xP (Confidence: {rec.confidence_score:.0f}%)")
            print(f"     Strategic Reason : {rec.trigger_reason}\n")

        print("=" * 85)
        print("📅 OPTIMAL CHIP CALENDAR SUMMARY:")
        for line in roadmap.optimal_calendar_summary:
            print(f"  • {line}")
        print("=" * 85)

    except Exception as e:
        print(f"\n[ERROR] Chip evaluation failed: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
