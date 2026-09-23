"""
Runnable script demonstrating all FPL & xG API calls.
Run this script to test all endpoints:
    python run_examples.py
"""
import json
from src.api.fpl_client import FPLClient
from src.api.understat_client import UnderstatClient


def demo_fpl_api():
    print("=" * 60)
    print("1. OFFICIAL FPL API - BOOTSTRAP STATIC (Players, Teams, xG)")
    print("=" * 60)
    
    client = FPLClient()
    
    # 1. Fetch all players as a Pandas DataFrame
    df = client.get_players_df()
    print(f"Total Players Loaded: {len(df)}")
    
    top_xg = df.sort_values(by="expected_goals", ascending=False)[
        ["web_name", "team_name", "position", "cost_m", "goals_scored", "expected_goals", "expected_assists", "total_points"]
    ].head(5)
    print("\nTop 5 Players by Expected Goals (xG):")
    print(top_xg.to_string(index=False))

    # 2. Individual Player Deep Dive
    print("\n" + "=" * 60)
    print("2. INDIVIDUAL PLAYER SUMMARY (Match History & Fixtures)")
    print("=" * 60)
    top_player_id = int(top_xg.iloc[0]["id"]) if "id" in top_xg else int(df.iloc[0]["id"])
    player_name = top_xg.iloc[0]["web_name"]
    print(f"Fetching summary for: {player_name} (ID: {top_player_id})")
    
    summary = client.get_element_summary(top_player_id)
    recent_matches = summary.get("history", [])[-3:] # Last 3 matches
    print(f"Last {len(recent_matches)} Matches Played:")
    for match in recent_matches:
        print(f"  - GW {match.get('round')}: Points={match.get('total_points')}, Min={match.get('minutes')}, Goals={match.get('goals_scored')}, xG={match.get('expected_goals')}, xA={match.get('expected_assists')}")
        
    upcoming_fixtures = summary.get("fixtures", [])[:3] # Next 3 fixtures
    print(f"Next {len(upcoming_fixtures)} Upcoming Fixtures:")
    for fix in upcoming_fixtures:
        print(f"  - GW {fix.get('event')}: Difficulty (FDR) = {fix.get('difficulty')}, Kickoff = {fix.get('kickoff_time')}")

    # 3. Premier League Fixtures
    print("\n" + "=" * 60)
    print("3. UPCOMING PREMIER LEAGUE FIXTURES")
    print("=" * 60)
    fixtures = client.get_fixtures()
    print(f"Total Fixtures loaded: {len(fixtures)}")
    unplayed = [f for f in fixtures if not f.get("finished")][:3]
    for fix in unplayed:
        print(f"  - GW {fix.get('event')}: Team {fix.get('team_h')} vs Team {fix.get('team_a')} (FDR Home: {fix.get('team_h_difficulty')}, Away: {fix.get('team_a_difficulty')})")

    # 4. FPL Manager & Team Loading
    print("\n" + "=" * 60)
    print("4. FPL MANAGER & TEAM SQUAD LISTINGS")
    print("=" * 60)
    demo_manager_id = 1  # Example Manager ID
    print(f"Loading Enriched Team Listing for Manager ID: {demo_manager_id}")
    try:
        team_data = client.get_manager_team(demo_manager_id)
        print(f"  Manager Name : {team_data['manager_name']}")
        print(f"  Team Name    : {team_data['team_name']}")
        print(f"  Gameweek     : {team_data['event_id']}")
        print(f"  Squad Value  : £{team_data['team_value_m']:.1f}m (Bank: £{team_data['bank_m']:.1f}m)")
        print(f"  Active Chip  : {team_data['active_chip'] or 'None'}")
        
        # Display Enriched DataFrame of Manager's Squad
        team_df = client.get_manager_team_df(demo_manager_id)
        print("\n  Full Squad Listing:")
        print(team_df[["pos_no", "role", "player", "team", "pos", "cost_m", "captaincy", "total_pts", "xG", "xA"]].to_string(index=False))

        # 5. Manager Squad Predictive Scoring & Optimization
        print("\n" + "=" * 60)
        print("5. SQUAD PREDICTIVE SCORING & LINEUP OPTIMIZATION")
        print("=" * 60)
        report = client.analyze_manager_squad(demo_manager_id)
        opt = report.optimization
        print(f"  Target Gameweek  : GW {report.target_gameweek}")
        print(f"  Optimal Formation: {opt.formation} (Projected Total: {opt.total_projected_xp:.1f} xP)")
        print(f"  Top Captain (C)  : {opt.recommended_captain.web_name} ({opt.recommended_captain.score_breakdown.expected_points:.2f} xP - Index: {opt.recommended_captain.score_breakdown.composite_score}/100)")
        print(f"  Vice Captain (VC): {opt.recommended_vice_captain.web_name} ({opt.recommended_vice_captain.score_breakdown.expected_points:.2f} xP)")
        
        analysis_df = client.get_squad_analysis_df(demo_manager_id)
        print("\n  Top 5 Projected Players:")
        print(analysis_df[["Player", "Team", "Pos", "Opponent (FDR)", "Form", "xP", "Score (0-100)", "Recommended Role"]].head(5).to_string(index=False))

    except Exception as e:
        print(f"  Could not load/analyze manager {demo_manager_id}: {e}")

    # 6. Understat xG & Advanced Metrics
    print("\n" + "=" * 60)
    print("6. UNDERSTAT ADVANCED STATS (xGChain & xGBuildup)")
    print("=" * 60)
    understat = UnderstatClient()
    try:
        understat_players = understat.get_league_players()
        if understat_players:
            print(f"Loaded {len(understat_players)} players from Understat.")
            print("Top 3 Players by xGChain:")
            sorted_by_chain = sorted(
                understat_players, 
                key=lambda x: float(x.get("xGChain", 0) or 0), 
                reverse=True
            )[:3]
            for p in sorted_by_chain:
                print(f"  - {p.get('player_name')} ({p.get('team_title')}): Goals={p.get('goals')}, xG={p.get('xG')}, xGChain={p.get('xGChain')}, xGBuildup={p.get('xGBuildup')}")
        else:
            print("Understat data parsing returned no players.")
    except Exception as e:
        print(f"Understat fetch failed: {e}")

    client.close()
    understat.close()
    print("\nDemo completed.")


if __name__ == "__main__":
    demo_fpl_api()
