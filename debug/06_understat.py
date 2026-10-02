"""
Debug Script: Understat Advanced xG Scraping
Run via UV: uv run debug/06_understat.py
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.understat_client import UnderstatClient

client = UnderstatClient()
print("Scraping Understat Premier League Data...")
players = client.get_league_players()

print(f"\n[OK] Loaded {len(players)} players from Understat.")
if players:
    print("\nTop 5 Players by xGChain (Overall Threat in Possessions):")
    top_chain = sorted(players, key=lambda x: float(x.get("xGChain", 0) or 0), reverse=True)[:5]
    for p in top_chain:
        print(f"  {p.get('player_name'):<20} ({p.get('team_title'):<12}) | xG={p.get('xG'):<5} | xGChain={p.get('xGChain'):<5} | xGBuildup={p.get('xGBuildup'):<5}")

client.close()
