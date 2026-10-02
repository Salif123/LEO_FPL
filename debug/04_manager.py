"""
Debug Script: FPL Manager & Team Squad Loading
Run via UV or Python:
    python debug/04_manager.py
    python debug/04_manager.py [manager_id] [gw]
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient

# If command-line arguments are provided, use them; otherwise, prompt interactively
if len(sys.argv) > 1:
    try:
        manager_id = int(sys.argv[1])
    except ValueError:
        manager_id = 1
    
    gw = None
    if len(sys.argv) > 2:
        try:
            gw = int(sys.argv[2])
        except ValueError:
            gw = None
else:
    print("=" * 60)
    print("⚽  FPL Manager Team Listing Debugger")
    print("=" * 60)
    mid_raw = input("Enter Manager ID [Default: 1]: ").strip()
    manager_id = int(mid_raw) if mid_raw else 1
    
    gw_raw = input("Enter Gameweek (1-38) or press Enter for Current: ").strip()
    gw = int(gw_raw) if gw_raw else None

client = FPLClient()
print(f"Fetching Team Listing for Manager ID: {manager_id}...")
try:
    team_data = client.get_manager_team(manager_id, gw)
    
    print("\n" + "=" * 75)
    print(f"  👤 MANAGER: {team_data['manager_name']} | TEAM: {team_data['team_name']}")
    print(f"  🎯 GAMEWEEK {team_data['event_id']} | CHIP: {team_data['active_chip'] or 'None'}")
    print(f"  💰 SQUAD VALUE: £{team_data['team_value_m']:.1f}m | BANK: £{team_data['bank_m']:.1f}m")
    print("=" * 75)

    print("\n⭐ STARTING XI:")
    print(f"{'Pos':<5} | {'Player':<20} | {'Team':<12} | {'Role':<5} | {'Cost':<7} | {'Pts':<5} | {'Form':<5} | {'xG':<5} | {'xA':<5} | {'Status'}")
    print("-" * 80)
    for p in team_data["starting_xi"]:
        cap_tag = " (C)" if p["is_captain"] else (" (VC)" if p["is_vice_captain"] else "")
        player_str = f"{p['web_name']}{cap_tag}"
        print(f"#{p['squad_position']:<4} | {player_str:<20} | {p['team_short_name']:<12} | {p['position']:<5} | £{p['cost_m']:<5.1f} | {p['total_points']:<5} | {p['form']:<5.1f} | {p['expected_goals']:<5.2f} | {p['expected_assists']:<5.2f} | {p['status']}")

    print("\n🪑 BENCH:")
    print(f"{'Pos':<5} | {'Player':<20} | {'Team':<12} | {'Role':<5} | {'Cost':<7} | {'Pts':<5} | {'Form':<5} | {'xG':<5} | {'xA':<5} | {'Status'}")
    print("-" * 80)
    for p in team_data["bench"]:
        sub_label = f"Sub {p['squad_position'] - 11}"
        cap_tag = " (VC)" if p["is_vice_captain"] else ""
        player_str = f"{p['web_name']}{cap_tag}"
        print(f"#{p['squad_position']:<4} | {player_str:<20} | {p['team_short_name']:<12} | {p['position']:<5} | £{p['cost_m']:<5.1f} | {p['total_points']:<5} | {p['form']:<5.1f} | {p['expected_goals']:<5.2f} | {p['expected_assists']:<5.2f} | {p['status']}")

    print("\n" + "=" * 75)
    print("📊 PANDAS DATAFRAME VIEW:")
    print("=" * 75)
    df = client.get_manager_team_df(manager_id, gw)
    print(df.to_string(index=False))

except Exception as e:
    print(f"\n[ERROR] Failed to load manager team: {e}")

finally:
    client.close()

