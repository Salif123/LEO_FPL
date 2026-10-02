"""
Debug Script: Individual Player Element Summary
Run via UV or Python:
    python debug/02_player.py
    python debug/02_player.py [player_id]
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient

if len(sys.argv) > 1:
    try:
        player_id = int(sys.argv[1])
    except ValueError:
        player_id = 355
else:
    pid_in = input("Enter Player ID [Default: 355 (Haaland)]: ").strip()
    player_id = int(pid_in) if pid_in else 355

client = FPLClient()
print(f"Fetching Player Summary for Element ID {player_id}...")
summary = client.get_element_summary(player_id)

history = summary.get("history", [])
fixtures = summary.get("fixtures", [])

print(f"\n[OK] Match history records: {len(history)}")
print(f"[OK] Upcoming fixtures    : {len(fixtures)}")

if history:
    print("\nRecent Match Performance:")
    for m in history[-3:]:
        print(f"  GW {m['round']}: Minutes={m['minutes']}, Pts={m['total_points']}, xG={m['expected_goals']}, xA={m['expected_assists']}, Goals={m['goals_scored']}")

if fixtures:
    print("\nNext Fixture:")
    next_f = fixtures[0]
    print(f"  GW {next_f['event']} | FDR Difficulty={next_f['difficulty']} | Kickoff={next_f['kickoff_time']}")

client.close()
