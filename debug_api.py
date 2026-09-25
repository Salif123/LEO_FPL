"""
Comprehensive Interactive Debugger & Benchmarking Hub for FPL & Football Statistics.

Commands:
    python debug_api.py                             # Interactive Menu
    python debug_api.py bootstrap                   # Debug Bootstrap-static
    python debug_api.py player 355                  # Debug Player Summary (e.g. Haaland)
    python debug_api.py fixtures --gw 5             # Debug Gameweek Fixtures
    python debug_api.py live 5                      # Debug Live Matchday stats
    python debug_api.py manager 1 --gw 5            # Debug Manager squad & history
    python debug_api.py analyze 1                   # Debug Single-GW Squad Scoring & Lineup
    python debug_api.py horizon 1 --horizon 5       # Debug Multi-GW Horizon & Fixture Swings
    python debug_api.py transfers 1 --ft 1          # Debug Combinatorial Transfer Optimizer
    python debug_api.py chips 1                     # Debug Seasonal Chip Strategy Roadmap
    python debug_api.py league 314 --id 1209336     # Debug Mini-League & Effective Ownership
    python debug_api.py fusion                      # Debug Understat Data Fusion
    python debug_api.py cache                       # Debug Cache Performance & Latency
    python debug_api.py ping-all                    # Run Health Check on all APIs
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
from src.cache.cache_manager import get_cache
from src.config import FPLConfig, UnderstatConfig


def print_section(title: str):
    print("\n" + "=" * 75)
    print(f"  🔍 DEBUG: {title}")
    print("=" * 75)


def format_size(byte_count: int) -> str:
    if byte_count < 1024:
        return f"{byte_count} B"
    elif byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.2f} KB"
    return f"{byte_count / (1024 * 1024):.2f} MB"


def benchmark_get(url: str, params: Optional[Dict[str, Any]] = None) -> tuple[int, float, int, Any, Dict[str, str]]:
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
    
    if isinstance(data, dict):
        elements = data.get("elements", [])
        teams = data.get("teams", [])
        events = data.get("events", [])
        print(f"\nSummary:")
        print(f"  • Total Players : {len(elements)}")
        print(f"  • Total Clubs   : {len(teams)}")
        print(f"  • Total Events  : {len(events)}")


# -------------------------------------------------------------------------
# 2. Debug Player Summary
# -------------------------------------------------------------------------
def debug_player(player_id: int):
    print_section(f"Player Element Summary (ID: {player_id})")
    url = FPLConfig.ELEMENT_SUMMARY_URL.format(player_id=player_id)
    status, latency, size, data, _ = benchmark_get(url)
    print(f"Status: {status} | Latency: {latency:.1f} ms | Size: {format_size(size)}")
    
    if status == 200 and isinstance(data, dict):
        history = data.get("history", [])
        fixtures = data.get("fixtures", [])
        print(f"Matches Played: {len(history)} | Upcoming Fixtures: {len(fixtures)}")


# -------------------------------------------------------------------------
# 3. Debug Fixtures
# -------------------------------------------------------------------------
def debug_fixtures(gw: Optional[int] = None):
    print_section(f"Premier League Fixtures {'(All Season)' if not gw else f'(Gameweek {gw})'}")
    url = FPLConfig.FIXTURES_URL
    params = {"event": gw} if gw else None
    status, latency, size, data, _ = benchmark_get(url, params=params)
    print(f"Status: {status} | Latency: {latency:.1f} ms | Size: {format_size(size)}")
    if isinstance(data, list):
        print(f"Total Fixtures Returned: {len(data)}")


# -------------------------------------------------------------------------
# 4. Debug Live Matchday
# -------------------------------------------------------------------------
def debug_live(gw: int):
    print_section(f"Live Gameweek Matchday Data (GW: {gw})")
    url = FPLConfig.EVENT_LIVE_URL.format(event_id=gw)
    status, latency, size, data, _ = benchmark_get(url)
    print(f"Status: {status} | Latency: {latency:.1f} ms | Size: {format_size(size)}")


# -------------------------------------------------------------------------
# 5. Debug Manager Team
# -------------------------------------------------------------------------
def debug_manager(manager_id: int, gw: Optional[int] = None):
    print_section(f"Manager Team Loading (Manager ID: {manager_id})")
    client = FPLClient()
    try:
        team_data = client.get_manager_team(manager_id, gw)
        print(f"Manager: {team_data['manager_name']} | Team: {team_data['team_name']}")
        print(f"GW: {team_data['event_id']} | Value: £{team_data['team_value_m']:.1f}m | Bank: £{team_data['bank_m']:.1f}m")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()


# -------------------------------------------------------------------------
# 6. Debug Squad Analysis & Scoring
# -------------------------------------------------------------------------
def debug_analysis(manager_id: int, gw: Optional[int] = None):
    print_section(f"Manager Squad Analysis (Manager ID: {manager_id})")
    client = FPLClient()
    try:
        report = client.analyze_manager_squad(manager_id, gw)
        opt = report.optimization
        print(f"Target GW: {report.target_gameweek} | Formation: {opt.formation} | Projected Total: {opt.total_projected_xp:.1f} xP")
        print(f"Captain: {opt.recommended_captain.web_name} ({opt.recommended_captain.score_breakdown.expected_points:.1f} xP)")
        print(f"Vice-Captain: {opt.recommended_vice_captain.web_name}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()


# -------------------------------------------------------------------------
# 7. Debug Multi-GW Horizon & Fixture Swings
# -------------------------------------------------------------------------
def debug_horizon(manager_id: int, horizon_length: int = 5, start_gw: Optional[int] = None):
    print_section(f"Multi-GW Horizon Engine (Manager ID: {manager_id}, Length: {horizon_length} GWs)")
    client = FPLClient()
    try:
        report = client.analyze_manager_horizon(manager_id, horizon_length=horizon_length, start_gw=start_gw)
        print(f"Window: GW {report.start_gameweek}-{report.end_gameweek} | Total Horizon xP: {report.total_horizon_xp:.1f} pts (Avg: {report.avg_xp_per_gw:.1f}/GW)")
        print("\nUpcoming League Fixture Swings:")
        for sw in report.fixture_swings[:4]:
            print(f"  • {sw.team_name:<20} : Avg FDR {sw.fdr_avg:.2f} -> {sw.sentiment}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()


# -------------------------------------------------------------------------
# 8. Debug Combinatorial Transfers
# -------------------------------------------------------------------------
def debug_transfers(manager_id: int, free_transfers: int = 1, horizon_length: int = 4):
    print_section(f"Combinatorial Transfer Optimizer (Manager ID: {manager_id}, FTs: {free_transfers})")
    client = FPLClient()
    try:
        report = client.optimize_transfers(manager_id, free_transfers=free_transfers, horizon_length=horizon_length)
        if report.best_overall_recommendation:
            b = report.best_overall_recommendation
            print(f"Top Move: {b.rationale}")
            print(f"Net Horizon Gain: +{b.net_horizon_gain:.2f} xP (Breaks even in GW {b.break_even_gw})")
        else:
            print("No viable upgrades exceeding hit penalties found.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()


# -------------------------------------------------------------------------
# 9. Debug Chip Strategy
# -------------------------------------------------------------------------
def debug_chips(manager_id: int):
    print_section(f"Seasonal Chip Strategy Roadmap (Manager ID: {manager_id})")
    client = FPLClient()
    try:
        roadmap = client.evaluate_chips(manager_id)
        print(f"Remaining Chips: {', '.join(c.upper() for c in roadmap.chips_remaining) if roadmap.chips_remaining else 'None'}")
        for rec in roadmap.recommendations:
            print(f"  • {rec.chip_name.upper():<14} -> Target GW {rec.recommended_gw} (+{rec.projected_upside_xp:.1f} xP): {rec.trigger_reason}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()


# -------------------------------------------------------------------------
# 10. Debug Mini-League & Effective Ownership (EO)
# -------------------------------------------------------------------------
def debug_league(league_id: int, manager_id: Optional[int] = None):
    print_section(f"Mini-League & Effective Ownership (League ID: {league_id})")
    client = FPLClient()
    try:
        from src.analysis.league_analyzer import LeagueAnalyzer
        analyzer = LeagueAnalyzer(client)
        report = analyzer.analyze_mini_league(league_id, target_manager_id=manager_id)
        
        print(f"League: {report.league_name} | Total Managers: {report.total_managers}")
        print("\nCaptaincy Distribution:")
        for cap, pct in list(report.top_captains_distribution.items())[:3]:
            print(f"  • {cap:<18} : {pct:>5.1f}%")
            
        print("\nTop 5 Effective Ownership (EO) Players:")
        for eo in report.effective_ownership[:5]:
            print(f"  • {eo.web_name:<18} ({eo.team_short_name}) : EO {eo.effective_ownership_pct:>5.1f}% | {eo.threat_sentiment}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()


# -------------------------------------------------------------------------
# 11. Debug Understat Fusion
# -------------------------------------------------------------------------
def debug_fusion():
    print_section("Understat & FPL Data Fusion")
    from src.analysis.understat_fusion import UnderstatFusion
    fpl_client = FPLClient()
    understat_client = UnderstatClient()
    try:
        bootstrap = fpl_client.get_bootstrap_static()
        u_players = understat_client.get_league_players()
        fusion = UnderstatFusion(u_players)
        
        sample_player = fusion.match_player("Haaland", "Erling", "Haaland", "Man City")
        if sample_player:
            print(f"Matched: {sample_player.player_name} ({sample_player.team_title})")
            print(f"npxG90: {sample_player.npxG90} | xA90: {sample_player.xA90} | xGChain90: {sample_player.xGChain90} | xG Delta: {sample_player.xg_delta:+0.2f}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        fpl_client.close()
        understat_client.close()


# -------------------------------------------------------------------------
# 12. Debug Cache Performance
# -------------------------------------------------------------------------
def debug_cache():
    print_section("Cache Performance & Latency Benchmark")
    cache = get_cache()
    fpl_client = FPLClient(cache=cache)
    
    # Cold
    cache.clear()
    start = time.perf_counter()
    fpl_client.get_bootstrap_static(use_cache=True)
    cold_ms = (time.perf_counter() - start) * 1000

    # Warm
    start = time.perf_counter()
    fpl_client.get_bootstrap_static(use_cache=True)
    warm_ms = (time.perf_counter() - start) * 1000

    print(f"Bootstrap Static Cold Network Latency : {cold_ms:.1f} ms")
    print(f"Bootstrap Static Warm Cache Latency   : {warm_ms:.2f} ms")
    print(f"Speedup Factor                        : {cold_ms / warm_ms:.0f}x faster")
    fpl_client.close()


# -------------------------------------------------------------------------
# 13. Ping All Endpoints
# -------------------------------------------------------------------------
def ping_all():
    print_section("Health Check & Latency Ping on All APIs")
    endpoints = [
        ("FPL Bootstrap Static", FPLConfig.BOOTSTRAP_STATIC_URL, None),
        ("FPL Fixtures", FPLConfig.FIXTURES_URL, None),
        ("FPL Element Summary (Haaland #355)", FPLConfig.ELEMENT_SUMMARY_URL.format(player_id=355), None),
        ("FPL Event Live (GW 1)", FPLConfig.EVENT_LIVE_URL.format(event_id=1), None),
        ("FPL Manager Entry (#1)", FPLConfig.MANAGER_ENTRY_URL.format(manager_id=1), None),
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
    parser = argparse.ArgumentParser(description="FPL Analyzer & Football Stats API Hub")
    parser.add_argument("command", nargs="?", choices=[
        "bootstrap", "player", "fixtures", "live", "manager", "analyze",
        "horizon", "transfers", "chips", "league", "fusion", "cache", "ping-all", "menu"
    ], help="Command to run")
    parser.add_argument("id", nargs="?", type=int, help="Player ID or Manager ID or League ID")
    parser.add_argument("--gw", type=int, help="Gameweek ID")
    parser.add_argument("--horizon", type=int, default=5, help="Horizon Length in Gameweeks")
    parser.add_argument("--ft", type=int, default=1, help="Available Free Transfers (1-5)")
    parser.add_argument("--mid", type=int, help="Optional Manager ID for League comparison")

    args = parser.parse_args()

    if args.command == "bootstrap":
        debug_bootstrap()
    elif args.command == "player":
        debug_player(args.id or 355)
    elif args.command == "fixtures":
        debug_fixtures(args.gw)
    elif args.command == "live":
        debug_live(args.id or args.gw or 1)
    elif args.command == "manager":
        debug_manager(args.id or 1, args.gw)
    elif args.command == "analyze":
        debug_analysis(args.id or 1, args.gw)
    elif args.command == "horizon":
        debug_horizon(args.id or 1, horizon_length=args.horizon, start_gw=args.gw)
    elif args.command == "transfers":
        debug_transfers(args.id or 1, free_transfers=args.ft, horizon_length=args.horizon)
    elif args.command == "chips":
        debug_chips(args.id or 1)
    elif args.command == "league":
        debug_league(args.id or 314, manager_id=args.mid)
    elif args.command == "fusion":
        debug_fusion()
    elif args.command == "cache":
        debug_cache()
    elif args.command == "ping-all":
        ping_all()
    else:
        # Interactive Menu
        print("\n" + "=" * 65)
        print("⚽  FPL ANALYZER & STATS API INTERACTIVE DEBUGGER")
        print("=" * 65)
        print(" 1. Bootstrap Static (Players, Teams, Events)")
        print(" 2. Individual Player Deep-Dive (History & Fixtures)")
        print(" 3. Premier League Fixtures")
        print(" 4. Live Gameweek Matchday Points")
        print(" 5. Manager & Team Squad Loading")
        print(" 6. Single-GW Squad Scoring & Optimal Lineup")
        print(" 7. Multi-GW Horizon Projections (3-8 GWs) & Fixture Swings")
        print(" 8. Combinatorial Transfer Optimizer (1/2 Swaps & Hits)")
        print(" 9. Seasonal Chip Strategy Roadmap (WC, FH, BB, TC)")
        print("10. Mini-League Tracker & Effective Ownership (EO)")
        print("11. Understat & FPL Data Fusion (npxG90, xGChain90)")
        print("12. Cache Latency & Performance Benchmark")
        print("13. Ping & Benchmark All Endpoints")
        print(" 0. Exit")
        print("=" * 65)

        choice = input("Select an option [0-13]: ").strip()
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
            mid = input("Enter Manager ID [Default: 1]: ").strip()
            debug_analysis(int(mid) if mid else 1)
        elif choice == "7":
            mid = input("Enter Manager ID [Default: 1]: ").strip()
            hl = input("Enter Horizon Length [Default: 5]: ").strip()
            debug_horizon(int(mid) if mid else 1, horizon_length=int(hl) if hl else 5)
        elif choice == "8":
            mid = input("Enter Manager ID [Default: 1]: ").strip()
            ft = input("Enter Free Transfers (1-5) [Default: 1]: ").strip()
            debug_transfers(int(mid) if mid else 1, free_transfers=int(ft) if ft else 1)
        elif choice == "9":
            mid = input("Enter Manager ID [Default: 1]: ").strip()
            debug_chips(int(mid) if mid else 1)
        elif choice == "10":
            lid = input("Enter Mini-League ID [Default: 314]: ").strip()
            mid = input("Enter Your Manager ID (optional): ").strip()
            debug_league(int(lid) if lid else 314, manager_id=int(mid) if mid else None)
        elif choice == "11":
            debug_fusion()
        elif choice == "12":
            debug_cache()
        elif choice == "13":
            ping_all()
        else:
            print("Exiting.")


if __name__ == "__main__":
    main()
