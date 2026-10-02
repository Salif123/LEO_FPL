"""
Debug Script: Understat & FPL Data Fusion
Tests fuzzy matching, per-90 underlying statistics (npxG90, xA90, xGChain90, xGBuildup90),
and DataFrame enrichment.

Run:
    python debug/08_understat_fusion.py
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient
from src.api.understat_client import UnderstatClient
from src.analysis.understat_fusion import UnderstatFusion


def main():
    print("=" * 80)
    print("🔬  DEBUG: Understat & FPL Data Fusion Engine")
    print("=" * 80)

    fpl_client = FPLClient()
    understat_client = UnderstatClient()

    print("\n1. Fetching FPL Bootstrap Data...")
    bootstrap = fpl_client.get_bootstrap_static()
    elements = bootstrap.get("elements", [])
    teams = {t["id"]: t for t in bootstrap.get("teams", [])}
    print(f"   ✓ Loaded {len(elements)} FPL players across 20 clubs.")

    print("\n2. Fetching Understat EPL Dataset...")
    u_players = understat_client.get_league_players()
    print(f"   ✓ Loaded {len(u_players)} Understat records.")

    if not u_players:
        print("   ⚠️ Understat returned no data (might be offseason/network). Continuing with sample.")
    
    fusion = UnderstatFusion(u_players)

    print("\n3. Testing Fuzzy Player Name & Club Matching:")
    test_queries = [
        ("Haaland", "Erling", "Haaland", "Man City"),
        ("Salah", "Mohamed", "Salah", "Liverpool"),
        ("Saka", "Bukayo", "Saka", "Arsenal"),
        ("Palmer", "Cole", "Palmer", "Chelsea"),
        ("Son", "Heung-min", "Son", "Spurs"),
        ("Watkins", "Ollie", "Watkins", "Aston Villa"),
        ("Isak", "Alexander", "Isak", "Newcastle"),
        ("Gabriel", "Gabriel", "dos Santos Magalhães", "Arsenal"),
        ("Bruno Fernandes", "Bruno", "Borges Fernandes", "Man Utd"),
        ("Cunha", "Matheus", "Santos Carneiro Da Cunha", "Wolves"),
    ]

    print(f"{'FPL Query':<20} | {'Understat Match':<22} | {'Team':<16} | {'npxG90':<7} | {'xA90':<6} | {'xGChain90':<10} | {'xG Delta'}")
    print("-" * 100)

    matched_count = 0
    for web, first, second, team in test_queries:
        matched = fusion.match_player(web, first, second, team)
        if matched:
            matched_count += 1
            print(f"{web:<20} | {matched.player_name:<22} | {matched.team_title:<16} | {matched.npxG90:<7.2f} | {matched.xA90:<6.2f} | {matched.xGChain90:<10.2f} | {matched.xg_delta:>+5.2f}")
        else:
            print(f"{web:<20} | ❌ NOT MATCHED        | {team:<16} | {'N/A':<7} | {'N/A':<6} | {'N/A':<10} | N/A")

    print("-" * 100)
    print(f"Matching Accuracy on Test Pool: {matched_count}/{len(test_queries)} ({matched_count/len(test_queries)*100:.0f}%)")

    print("\n4. Generating Enriched Player DataFrame (FPL + Understat):")
    players_df = fpl_client.get_players_df()
    enriched_df = fusion.enrich_players_df(players_df, elements, teams)
    
    # Show top 10 players by xGChain90 (min 300 mins)
    qualified = enriched_df[enriched_df["minutes"] >= 300].sort_values(by="understat_xgchain90", ascending=False)
    print("\nTop 10 EPL Players by xGChain90 (Min 300 mins):")
    cols = ["web_name", "team_name", "position", "cost_m", "understat_npxg90", "understat_xa90", "understat_xgchain90", "understat_xg_delta"]
    print(qualified[cols].head(10).to_string(index=False))

    fpl_client.close()
    understat_client.close()
    print("\n✓ Understat Fusion Debug Complete.")


if __name__ == "__main__":
    main()
