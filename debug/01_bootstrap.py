"""
Debug Script: FPL Bootstrap Static
Run via UV: uv run debug/01_bootstrap.py
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient

client = FPLClient()
print("Fetching Bootstrap Static data...")
data = client.get_bootstrap_static()

print(f"\n[OK] Keys in payload: {list(data.keys())}")
print(f"Total Players (elements)   : {len(data.get('elements', []))}")
print(f"Total Teams (teams)        : {len(data.get('teams', []))}")
print(f"Total Gameweeks (events)   : {len(data.get('events', []))}")

df = client.get_players_df()
print("\nTop 5 by Expected Goals (xG):")
print(df.sort_values(by="expected_goals", ascending=False)[["web_name", "team_name", "cost_m", "expected_goals", "goals_scored", "total_points"]].head())

client.close()
