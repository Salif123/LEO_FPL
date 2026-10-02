"""
Debug Script: Fixtures
Run via UV or Python:
    python debug/03_fixtures.py
    python debug/03_fixtures.py [gw]
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
        gw = None
else:
    gw_in = input("Enter Gameweek (1-38) or press Enter for All: ").strip()
    gw = int(gw_in) if gw_in else None

client = FPLClient()
print(f"Fetching Fixtures {'for Gameweek ' + str(gw) if gw else 'for Entire Season'}...")
fixtures = client.get_fixtures(event_id=gw)

print(f"\n[OK] Loaded {len(fixtures)} fixtures.")
upcoming = [f for f in fixtures if not f.get("finished")]
print(f"Upcoming Matches: {len(upcoming)}")

for f in upcoming[:5]:
    print(f"  GW {f.get('event')}: Team {f.get('team_h')} vs Team {f.get('team_a')} (Kickoff: {f.get('kickoff_time')})")

client.close()
