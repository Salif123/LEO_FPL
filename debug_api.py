"""
Comprehensive API Debugger for FPL & Football Statistics.

Usage via UV:
    uv run debug_api.py                             # Interactive Menu
    uv run debug_api.py bootstrap                   # Debug Bootstrap-static (xG, players, teams)
    uv run debug_api.py player 355                  # Debug Player Summary (e.g. Haaland)
    uv run debug_api.py fixtures --gw 5             # Debug Gameweek Fixtures
    uv run debug_api.py live 5                      # Debug Live Gameweek Matchday stats
    uv run debug_api.py manager 1 --gw 5            # Debug Manager profile, picks, squad, transfers
    uv run debug_api.py league 314                  # Debug Classic Mini-League
    uv run debug_api.py understat                   # Debug Understat Scraping (xG, xGChain)
    uv run debug_api.py ping-all                    # Run Health Check & Latency Benchmark on all APIs
"""

import argparse
import json
import sys
import time
from typing import Any, Dict, Optional
import requests

from src.api.base_client import BaseClient, ResourceNotFoundError, RateLimitError
from src.api.fpl_client import FPLClient
from src.api.understat_client import UnderstatClient
from src.config import FPLConfig, UnderstatConfig


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  🔍 DEBUG: {title}")
    print("=" * 70)


def format_size(byte_count: int) -> str:
    if byte_count < 1024:
        return f"{byte_count} B"
    elif byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.2f} KB"
    return f"{byte_count / (1024 * 1024):.2f} MB"


def benchmark_get(url: str, params: Optional[Dict[str, Any]] = None) -> tuple[int, float, int, Any, Dict[str, str]]:
    """Helper to perform timed request and return status, latency, size, data, headers."""
    session = requests.Session()
    headers = {
        "User-Agent": FPLConfig.USER_AGENT,
        "Accept": "application/json, text/plain, */*"
    }
    start = time.perf_counter()
    resp = session.get(url, params=params, headers=headers, timeout=15)
    latency_ms = (time.perf_counter() - start) * 1000
    size_bytes = len(resp.content)
    
    try:
        data = resp.json()
    except Exception:
        data = resp.text
        
    return resp.status_code, latency_ms, size_bytes, data, dict(resp.headers)


# -------------------------------------------------------------------------
# 1. Debug Bootstrap Static
# -------------------------------------------------------------------------
def debug_bootstrap():
    print_section("Official FPL Bootstrap Static")
    url = FPLConfig.BOOTSTRAP_STATIC_URL
    print(f"URL: {url}")
    
    status, latency, size, data, headers = benchmark_get(url)
    print(f"Status       : {status} OK")
    print(f"Latency      : {latency:.1f} ms")
    print(f"Payload Size : {format_size(size)}")
    print(f"Content-Type : {headers.get('Content-Type', 'N/A')}")
    
    if isinstance(data, dict):
        print(f"\nTop-Level Keys Found ({len(data.keys())}):")
        for key in data.keys():
            val = data[key]
            item_count = len(val) if isinstance(val, list) else (len(val.keys()) if isinstance(val, dict) else "scalar")
            print(f"  • '{key}': {type(val).__name__} (items: {item_count})")
            
        elements = data.get("elements", [])
        if elements:
            sample = elements[0]
            print(f"\nSample Player Object ('{sample.get('web_name')}', ID: {sample.get('id')}):")
            xg_keys = ["expected_goals", "expected_assists", "expected_goal_involvements", "expected_goals_conceded", "ict_index", "form", "now_cost", "selected_by_percent"]
            for k in xg_keys:
                print(f"  - {k:<28} : {sample.get(k)} (type: {type(sample.get(k)).__name__})")
                
        events = data.get("events", [])
        current_gw = next((e for e in events if e.get("is_current")), None)
        next_gw = next((e for e in events if e.get("is_next")), None)
        print(f"\nGameweek Status:")
        print(f"  - Current Gameweek : {current_gw['id'] if current_gw else 'None / Offseason'}")
        print(f"  - Next Gameweek    : {next_gw['id'] if next_gw else 'None'}")
        if next_gw:
            print(f"  - Next Deadline    : {next_gw.get('deadline_time')}")


# -------------------------------------------------------------------------
# 2. Debug Player Element Summary
# -------------------------------------------------------------------------
def debug_player(player_id: int):
    print_section(f"Player Element Summary (ID: {player_id})")
    url = FPLConfig.ELEMENT_SUMMARY_URL.format(player_id=player_id)
    print(f"URL: {url}")
    
    status, latency, size, data, _ = benchmark_get(url)
    print(f"Status       : {status}")
    print(f"Latency      : {latency:.1f} ms")
    print(f"Payload Size : {format_size(size)}")
    
    if status != 200:
        print(f"❌ Error fetching player: Status {status}")
        return

    history = data.get("history", [])
    fixtures = data.get("fixtures", [])
    history_past = data.get("history_past", [])
    
    print(f"\nSummary Sections:")
    print(f"  • Current Season Matches Played : {len(history)}")
    print(f"  • Remaining Fixtures            : {len(fixtures)}")
    print(f"  • Past Seasons on Record        : {len(history_past)}")
    
    if history:
        print("\nLast 3 Matches Breakdown:")
        for m in history[-3:]:
            print(f"  - GW {m.get('round')}: Min={m.get('minutes')} | Pts={m.get('total_points')} | Goals={m.get('goals_scored')} | xG={m.get('expected_goals')} | xA={m.get('expected_assists')} | BPS={m.get('bps')}")
            
    if fixtures:
        print("\nNext 3 Fixtures Breakdown:")
        for f in fixtures[:3]:
            loc = "Home" if f.get("is_home") else "Away"
            print(f"  - GW {f.get('event')}: vs Team {f.get('team_a' if f.get('is_home') else 'team_h')} ({loc}) | FDR Difficulty = {f.get('difficulty')} | Kickoff = {f.get('kickoff_time')}")


# -------------------------------------------------------------------------
# 3. Debug Fixtures
# -------------------------------------------------------------------------
def debug_fixtures(gw: Optional[int] = None):
    print_section(f"Premier League Fixtures {'(All Season)' if not gw else f'(Gameweek {gw})'}")
    url = FPLConfig.FIXTURES_URL
    params = {"event": gw} if gw else None
    print(f"URL   : {url}")
    print(f"Params: {params}")
    
    status, latency, size, data, _ = benchmark_get(url, params=params)
    print(f"Status       : {status}")
    print(f"Latency      : {latency:.1f} ms")
    print(f"Payload Size : {format_size(size)}")
    
    if isinstance(data, list):
        print(f"Total Fixtures Returned: {len(data)}")
        finished = [f for f in data if f.get("finished")]
        upcoming = [f for f in data if not f.get("finished")]
        print(f"  • Finished Fixtures : {len(finished)}")
        print(f"  • Upcoming Fixtures : {len(upcoming)}")
        
        if upcoming:
            print("\nNext 3 Scheduled Matches:")
            for f in upcoming[:3]:
                print(f"  - GW {f.get('event')}: Team {f.get('team_h')} vs Team {f.get('team_a')} (Home FDR: {f.get('team_h_difficulty')}, Away FDR: {f.get('team_a_difficulty')}) @ {f.get('kickoff_time')}")


# -------------------------------------------------------------------------
# 4. Debug Live Gameweek Matchday
# -------------------------------------------------------------------------
def debug_live(gw: int):
    print_section(f"Live Gameweek Matchday Data (GW: {gw})")
    url = FPLConfig.EVENT_LIVE_URL.format(event_id=gw)
    print(f"URL: {url}")
    
    status, latency, size, data, _ = benchmark_get(url)
    print(f"Status       : {status}")
    print(f"Latency      : {latency:.1f} ms")
    print(f"Payload Size : {format_size(size)}")
    
    if status != 200:
        print(f"❌ Error: Status {status}")
        return
        
    elements = data.get("elements", [])
    print(f"Total Player Records in GW {gw}: {len(elements)}")
    if elements:
        # Find top points scored in this live event
        top_performers = sorted(elements, key=lambda x: x.get("stats", {}).get("total_points", 0), reverse=True)[:3]
        print(f"\nTop 3 Performers in GW {gw}:")
        for p in top_performers:
            st = p.get("stats", {})
            print(f"  - Player ID {p.get('id')}: Points={st.get('total_points')} | Goals={st.get('goals_scored')} | Assists={st.get('assists')} | xG={st.get('expected_goals')} | Bonus={st.get('bonus')} | BPS={st.get('bps')}")


# -------------------------------------------------------------------------
# 5. Debug Manager Team & Picks Loading
# -------------------------------------------------------------------------
def debug_manager(manager_id: int, gw: Optional[int] = None):
    print_section(f"Manager Team Loading (Manager ID: {manager_id})")
    
    client = FPLClient()
    try:
        team_data = client.get_manager_team(manager_id, gw)
        
        print(f"Manager Overview:")
        print(f"  • Name         : {team_data['manager_name']}")
        print(f"  • Team Name    : {team_data['team_name']}")
        print(f"  • Gameweek     : {team_data['event_id']}")
        print(f"  • Active Chip  : {team_data['active_chip'] or 'None'}")
        print(f"  • Squad Value  : £{team_data['team_value_m']:.1f}m (Bank: £{team_data['bank_m']:.1f}m)")
        
        hist = team_data.get("entry_history")
        if hist:
            print(f"  • GW Points    : {hist.get('points')} (Bench: {hist.get('points_on_bench')})")
            print(f"  • Overall Rank : {hist.get('overall_rank')}")
            print(f"  • Transfers    : {hist.get('event_transfers')} (Cost: -{hist.get('event_transfers_cost')} pts)")

        print(f"\n⭐ Starting XI ({len(team_data['starting_xi'])} Players):")
        print(f"{'Pos':<4} | {'Player':<20} | {'Team':<6} | {'Role':<5} | {'Cost':<7} | {'Pts':<5} | {'xG':<5} | {'xA':<5} | {'Status'}")
        print("-" * 80)
        for p in team_data["starting_xi"]:
            cap_tag = " (C)" if p["is_captain"] else (" (VC)" if p["is_vice_captain"] else "")
            print(f"#{p['squad_position']:<3} | {p['web_name'] + cap_tag:<20} | {p['team_short_name']:<6} | {p['position']:<5} | £{p['cost_m']:<5.1f} | {p['total_points']:<5} | {p['expected_goals']:<5.2f} | {p['expected_assists']:<5.2f} | {p['status']}")

        print(f"\n🪑 Bench ({len(team_data['bench'])} Players):")
        print(f"{'Pos':<4} | {'Player':<20} | {'Team':<6} | {'Role':<5} | {'Cost':<7} | {'Pts':<5} | {'xG':<5} | {'xA':<5} | {'Status'}")
        print("-" * 80)
        for p in team_data["bench"]:
            cap_tag = " (VC)" if p["is_vice_captain"] else ""
            print(f"#{p['squad_position']:<3} | {p['web_name'] + cap_tag:<20} | {p['team_short_name']:<6} | {p['position']:<5} | £{p['cost_m']:<5.1f} | {p['total_points']:<5} | {p['expected_goals']:<5.2f} | {p['expected_assists']:<5.2f} | {p['status']}")
            
    except ResourceNotFoundError:
        print(f"❌ Manager ID {manager_id} does not exist (404 Not Found).")
    except Exception as e:
        print(f"❌ Error fetching manager team: {e}")
    finally:
        client.close()



# -------------------------------------------------------------------------
# 6. Debug Squad Analysis & Player Scoring
# -------------------------------------------------------------------------
def debug_analysis(manager_id: int, gw: Optional[int] = None):
    print_section(f"Manager Squad Analysis & Predictive Scoring (Manager ID: {manager_id})")
    
    client = FPLClient()
    try:
        report = client.analyze_manager_squad(manager_id, gw)
        opt = report.optimization
        
        print(f"Manager Overview:")
        print(f"  • Name         : {report.manager_name} ({report.team_name})")
        print(f"  • Target GW    : GW {report.target_gameweek}" + (f" (Deadline: {report.next_deadline})" if report.next_deadline else ""))
        print(f"  • Best Lineup  : {opt.formation} Formation | Total Projected xP: {opt.total_projected_xp:.1f} pts")
        
        # 1. Top 3 Captaincy Hierarchy
        print(f"\n👑 Top 3 Captaincy Hierarchy:")
        for c in opt.captain_hierarchy:
            p = c.player
            fix_str = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'} FDR {f.difficulty})" for f in p.fixtures])
            print(f"  #{c.rank} {c.role_name:<28} : {p.web_name} ({p.team_short_name}) vs {fix_str} -> {c.expected_points:.2f} xP ({c.threat_index:.1f}/100)")
            print(f"     Rationale: {c.rationale}")

        # 2. Starting XI
        print(f"\n⭐ Recommended Starting XI ({opt.formation}):")
        print(f"{'Role':<12} | {'Player':<18} | {'Club':<5} | {'Opponent (FDR)':<16} | {'Form':<5} | {'xP':<5} | {'Score':<6} | {'Status'}")
        print("-" * 85)
        for p in opt.recommended_starting_xi:
            cap_badge = " (C)" if p.is_recommended_captain else (" (VC)" if p.is_recommended_vice_captain else "")
            fix_str = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'}-{f.difficulty})" for f in p.fixtures])
            pos_label = f"Starter ({p.position})"
            print(f"{pos_label:<12} | {p.web_name + cap_badge:<18} | {p.team_short_name:<5} | {fix_str:<16} | {p.form:<5.1f} | {p.score_breakdown.expected_points:<5.2f} | {p.score_breakdown.composite_score:<6.1f} | {p.status}")

        # 3. Bench Hierarchy
        print(f"\n🪑 Recommended Bench (Prioritized Sub Order):")
        print(f"{'Priority':<12} | {'Player':<18} | {'Club':<5} | {'Pos':<4} | {'Opponent (FDR)':<16} | {'xP':<5} | {'Score':<6} | {'Status'}")
        print("-" * 85)
        for p in opt.recommended_bench:
            fix_str = ", ".join([f"{f.opponent_short_name} ({'H' if f.is_home else 'A'}-{f.difficulty})" for f in p.fixtures])
            print(f"{p.recommended_role:<12} | {p.web_name:<18} | {p.team_short_name:<5} | {p.position:<4} | {fix_str:<16} | {p.score_breakdown.expected_points:<5.2f} | {p.score_breakdown.composite_score:<6.1f} | {p.status}")

        # 4. Bench Optimization & Auto-Sub Strategy
        if opt.lineup_changes or opt.bench_adjustments or opt.bench_comparison:
            print("\n🔄 Bench Optimization & Auto-Sub Strategy:")
            print("-" * 85)
            if opt.lineup_changes:
                print("  Starting XI vs Bench Movements:")
                for lc in opt.lineup_changes:
                    print(f"    • {lc}")
            
            if opt.bench_adjustments:
                print("\n  Recommended Bench Slot Swaps:")
                for ba in opt.bench_adjustments:
                    print(f"    • {ba}")

            print("\n  Bench Player Auto-Sub Functions:")
            for b_item in opt.bench_comparison:
                p = b_item.player
                print(f"    • {p.web_name:<14} ({p.team_short_name} - {p.position}) [{p.score_breakdown.expected_points:.2f} xP] : {b_item.tactical_tag}")

        # 5. Transfer Recommendations
        if opt.transfer_recommendations:
            print(f"\n🔄 Metric-Driven Transfer Recommendations:")
            print("-" * 85)
            for idx, tr in enumerate(opt.transfer_recommendations, 1):
                p_out = tr.player_out
                p_in = tr.player_in
                print(f"  Option {idx}:")
                print(f"    🔴 Transfer OUT : {p_out.web_name} ({p_out.team_short_name} - {p_out.position}) £{p_out.cost_m:.1f}m [{p_out.score_breakdown.expected_points:.2f} xP]")
                print(f"       Reason       : {tr.out_reason}")
                print(f"    🟢 Transfer IN  : {p_in.web_name} ({p_in.team_short_name} - {p_in.position}) £{p_in.cost_m:.1f}m [{p_in.score_breakdown.expected_points:.2f} xP]")
                print(f"       Reason       : {tr.in_reason}")
                print(f"       Net Impact   : 📈 +{tr.expected_points_gain:.2f} xP Gain | Bank: £{tr.remaining_bank_m:.1f}m\n")

        if opt.risk_warnings:
            print(f"🚨 Tactical Warnings:")
            for w in opt.risk_warnings:
                print(f"  • {w}")

        # 6. Complete Squad Ranking Table
        print("\n" + "=" * 85)
        print("📊 COMPLETE SQUAD RANKING (SORTED BY xP):")
        print("=" * 85)
        df = client.get_squad_analysis_df(manager_id, gw)
        print(df[["Player", "Team", "Pos", "Opponent (FDR)", "Form", "xP", "Score (0-100)", "Recommended Role", "Status"]].to_string(index=False))

    except Exception as e:
        print(f"❌ Error analyzing squad: {e}")
    finally:
        client.close()


# -------------------------------------------------------------------------
# 7. Debug Understat Scraping
# -------------------------------------------------------------------------
def debug_understat():
    print_section("Understat Advanced xG Scraping")
    url = UnderstatConfig.LEAGUE_EPL_URL
    print(f"URL: {url}")
    
    status, latency, size, html, headers = benchmark_get(url)
    print(f"Status       : {status}")
    print(f"Latency      : {latency:.1f} ms")
    print(f"Payload Size : {format_size(size)}")
    
    client = UnderstatClient()
    players = client.get_league_players()
    print(f"\nExtracted Players Count: {len(players)}")
    
    if players:
        sample = players[0]
        print(f"\nSample Player Record ({sample.get('player_name')}, Team: {sample.get('team_title')}):")
        keys = ["goals", "xG", "assists", "xA", "npxG", "xGChain", "xGBuildup", "shots", "key_passes", "time"]
        for k in keys:
            print(f"  - {k:<15} : {sample.get(k)}")


# -------------------------------------------------------------------------
# 8. Ping / Benchmark All APIs
# -------------------------------------------------------------------------
def ping_all():
    print_section("Health Check & Latency Ping on All APIs")
    
    endpoints = [
        ("FPL Bootstrap Static", FPLConfig.BOOTSTRAP_STATIC_URL, None),
        ("FPL Fixtures", FPLConfig.FIXTURES_URL, None),
        ("FPL Element Summary (Haaland #355)", FPLConfig.ELEMENT_SUMMARY_URL.format(player_id=355), None),
        ("FPL Event Live (GW 1)", FPLConfig.EVENT_LIVE_URL.format(event_id=1), None),
        ("FPL Manager Entry (#1)", FPLConfig.MANAGER_ENTRY_URL.format(manager_id=1), None),
        ("FPL Manager Picks (#1 GW 1)", FPLConfig.MANAGER_PICKS_URL.format(manager_id=1, event_id=1), None),
        ("Understat Premier League", UnderstatConfig.LEAGUE_EPL_URL, None),
    ]
    
    print(f"{'Endpoint':<35} | {'Status':<7} | {'Latency':<9} | {'Size':<10}")
    print("-" * 70)
    
    for name, url, params in endpoints:
        try:
            status, latency, size, _, _ = benchmark_get(url, params)
            print(f"{name:<35} | {status:<7} | {latency:>6.1f} ms | {format_size(size):<10}")
        except Exception as e:
            print(f"{name:<35} | {'ERR':<7} | {'N/A':>9} | {str(e)[:20]}")


# -------------------------------------------------------------------------
# CLI & Interactive Entry Point
# -------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="FPL and Football Stats API Debugging Tool")
    parser.add_argument("command", nargs="?", choices=["bootstrap", "player", "fixtures", "live", "manager", "analyze", "understat", "ping-all", "menu"], help="API command to debug")
    parser.add_argument("id", nargs="?", type=int, help="Player ID or Manager ID or Gameweek ID")
    parser.add_argument("gw_pos", nargs="?", type=int, help="Optional Positional Gameweek ID")
    parser.add_argument("--gw", type=int, help="Gameweek / Event ID")
    
    args = parser.parse_args()
    
    if args.command == "bootstrap":
        debug_bootstrap()
    elif args.command == "player":
        pid = args.id
        if pid is None:
            pid_raw = input("Enter Player ID [Default: 355 (Haaland)]: ").strip()
            pid = int(pid_raw) if pid_raw else 355
        debug_player(pid)
    elif args.command == "fixtures":
        target_gw = args.gw or args.gw_pos
        debug_fixtures(target_gw)
    elif args.command == "live":
        gw = args.id or args.gw or args.gw_pos
        if gw is None:
            gw_raw = input("Enter Gameweek [Default: 1]: ").strip()
            gw = int(gw_raw) if gw_raw else 1
        debug_live(gw)
    elif args.command == "manager":
        mid = args.id
        target_gw = args.gw or args.gw_pos
        if mid is None:
            mid_raw = input("Enter Manager ID [Default: 1]: ").strip()
            mid = int(mid_raw) if mid_raw else 1
            gw_raw = input("Enter Gameweek or press Enter for Current: ").strip()
            target_gw = int(gw_raw) if gw_raw else None
        debug_manager(mid, target_gw)
    elif args.command == "analyze":
        client_tmp = FPLClient()
        bootstrap_tmp = client_tmp.get_bootstrap_static()
        from src.analysis.squad_analyzer import SquadAnalyzer
        analyzer_tmp = SquadAnalyzer(client_tmp)
        upcoming_gw, deadline = analyzer_tmp.get_upcoming_gameweek(bootstrap_tmp)
        client_tmp.close()

        mid = args.id
        cli_gw = args.gw or args.gw_pos
        if mid is None:
            print(f"\n📌 Upcoming Gameweek: GW {upcoming_gw}" + (f" (Deadline: {deadline})" if deadline else ""))
            mid_raw = input("Enter Manager ID [Default: 1]: ").strip()
            mid = int(mid_raw) if mid_raw else 1
            gw_raw = input(f"Enter Upcoming Gameweek [{upcoming_gw}-38] [Default: {upcoming_gw}]: ").strip()
            if gw_raw:
                try:
                    chosen = int(gw_raw)
                    target_gw = upcoming_gw if chosen < upcoming_gw else min(chosen, 38)
                except ValueError:
                    target_gw = upcoming_gw
            else:
                target_gw = upcoming_gw
        else:
            if cli_gw is not None:
                target_gw = upcoming_gw if cli_gw < upcoming_gw else min(cli_gw, 38)
            else:
                target_gw = upcoming_gw
        debug_analysis(mid, target_gw)
    elif args.command == "understat":
        debug_understat()
    elif args.command == "ping-all":
        ping_all()
    else:
        # Interactive Menu
        print("\n" + "=" * 60)
        print("⚽  FPL & Football Stats API Interactive Debugger")
        print("=" * 60)
        print("1. Debug Bootstrap Static (Players, Teams, xG fields)")
        print("2. Debug Individual Player Summary (History & FDR)")
        print("3. Debug Premier League Fixtures")
        print("4. Debug Live Gameweek Matchday Data")
        print("5. Debug Manager & Team Squad Loading")
        print("6. Debug Squad Analysis & Player Scoring (xP, FDR, Captaincy)")
        print("7. Debug Understat xG Scraper (xGChain, xGBuildup)")
        print("8. Ping / Benchmark All Endpoints")
        print("0. Exit")
        print("=" * 60)
        
        choice = input("Select an option [0-8]: ").strip()
        if choice == "1":
            debug_bootstrap()
        elif choice == "2":
            pid = input("Enter Player ID [Default: 355 (Haaland)]: ").strip()
            debug_player(int(pid) if pid else 355)
        elif choice == "3":
            gw_in = input("Enter Gameweek (1-38) or press Enter for All: ").strip()
            debug_fixtures(int(gw_in) if gw_in else None)
        elif choice == "4":
            gw_in = input("Enter Gameweek [Default: 1]: ").strip()
            debug_live(int(gw_in) if gw_in else 1)
        elif choice == "5":
            mid = input("Enter Manager ID [Default: 1]: ").strip()
            gw_in = input("Enter Gameweek or press Enter for Current: ").strip()
            debug_manager(int(mid) if mid else 1, int(gw_in) if gw_in else None)
        elif choice == "6":
            client_tmp = FPLClient()
            bootstrap_tmp = client_tmp.get_bootstrap_static()
            from src.analysis.squad_analyzer import SquadAnalyzer
            analyzer_tmp = SquadAnalyzer(client_tmp)
            upcoming_gw, deadline = analyzer_tmp.get_upcoming_gameweek(bootstrap_tmp)
            client_tmp.close()

            print(f"\n📌 Upcoming Gameweek: GW {upcoming_gw}" + (f" (Deadline: {deadline})" if deadline else ""))
            mid = input("Enter Manager ID [Default: 1]: ").strip()
            gw_in = input(f"Enter Upcoming Gameweek [{upcoming_gw}-38] [Default: {upcoming_gw}]: ").strip()
            
            target_gw = upcoming_gw
            if gw_in:
                try:
                    chosen = int(gw_in)
                    if chosen < upcoming_gw:
                        print(f"⚠️ GW {chosen} is in the past. Analyzing upcoming GW {upcoming_gw}.")
                        target_gw = upcoming_gw
                    else:
                        target_gw = min(chosen, 38)
                except ValueError:
                    target_gw = upcoming_gw

            debug_analysis(int(mid) if mid else 1, target_gw)
        elif choice == "7":
            debug_understat()
        elif choice == "8":
            ping_all()
        else:
            print("Exiting.")


if __name__ == "__main__":
    main()

