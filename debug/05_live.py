"""
Debug Script: Live Matchday Gameweek Data
Run via UV or Python:
    python debug/05_live.py
    python debug/05_live.py [gw]
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient

if len(sys.argv) > 1:
    try:
        gw = int(sys.argv[1])
    except ValueError:
        gw = 1
else:
    gw_in = input("Enter Gameweek [Default: 1]: ").strip()
    gw = int(gw_in) if gw_in else 1

client = FPLClient()
print(f"Fetching Live Stats for Gameweek {gw}...")
live = client.get_event_live(gw)

elements = live.get("elements", [])
print(f"\n[OK] Loaded live records for {len(elements)} players.")
if elements:
    top_scorers = sorted(elements, key=lambda x: x.get("stats", {}).get("total_points", 0), reverse=True)[:5]
    print("\nTop 5 Scorers in GW:")
    for p in top_scorers:
        st = p.get("stats", {})
        print(f"  Player ID {p.get('id')}: Points={st.get('total_points')}, Goals={st.get('goals_scored')}, xG={st.get('expected_goals')}, BPS={st.get('bps')}")

client.close()
