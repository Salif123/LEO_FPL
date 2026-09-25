"""
Debug Script: Combinatorial Multi-Transfer Optimizer
Evaluates 1-player, 2-player pair swaps, and 3-player mini-wildcards,
accounting for banked Free Transfers (1-5 FTs), point hit break-evens (-4/-8 pts),
and budget re-allocation across positions.

Run:
    python debug/10_transfer_optimizer.py [manager_id] [free_transfers] [horizon_length]
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient
from src.analysis.transfer_optimizer import TransferOptimizer


def main():
    client = FPLClient()
    bootstrap = client.get_bootstrap_static()
    from src.analysis.squad_analyzer import SquadAnalyzer
    analyzer = SquadAnalyzer(client)
    upcoming_gw, deadline = analyzer.get_upcoming_gameweek(bootstrap)

    manager_id = 1
    free_transfers = 1
    horizon_length = 4

    if len(sys.argv) > 1:
        try:
            manager_id = int(sys.argv[1])
        except ValueError:
            manager_id = 1
    else:
        print("=" * 80)
        print("🔄  COMBINATORIAL MULTI-TRANSFER & HIT OPTIMIZER")
        print("=" * 80)
        print(f"📌 Target Gameweek: GW {upcoming_gw}" + (f" (Deadline: {deadline})" if deadline else ""))
        mid_raw = input("Enter Manager ID [Default: 1]: ").strip()
        manager_id = int(mid_raw) if mid_raw else 1

        ft_raw = input("Enter Available Free Transfers (1-5) [Default: 1]: ").strip()
        free_transfers = int(ft_raw) if ft_raw else 1

        hl_raw = input("Enter Evaluation Horizon in GWs (1-6) [Default: 4]: ").strip()
        horizon_length = int(hl_raw) if hl_raw else 4

    if len(sys.argv) > 2:
        try:
            free_transfers = int(sys.argv[2])
        except ValueError:
            free_transfers = 1

    if len(sys.argv) > 3:
        try:
            horizon_length = int(sys.argv[3])
        except ValueError:
            horizon_length = 4

    print(f"\nRunning Combinatorial Transfer Analysis for Manager #{manager_id} (Horizon: {horizon_length} GWs, Free Transfers: {free_transfers})...")

    try:
        report = client.optimize_transfers(
            manager_id=manager_id,
            target_gw=upcoming_gw,
            horizon_length=horizon_length,
            free_transfers=free_transfers
        )

        print("\n" + "=" * 85)
        print(f"  🎯 TARGET GAMEWEEK : GW {report.target_gameweek} (Evaluating GW {report.target_gameweek}-{report.target_gameweek + report.horizon_length - 1})")
        print(f"  🎟️ FREE TRANSFERS  : {report.available_free_transfers} FTs | 💰 CURRENT BANK: £{report.current_bank_m:.1f}m")
        print("=" * 85)

        # 1. Single Transfers
        if report.single_transfers:
            print("\n1️⃣ TOP SINGLE TRANSFERS (1-FOR-1 SWAPS):")
            print("-" * 85)
            for idx, opt in enumerate(report.single_transfers, 1):
                p_out = opt.players_out[0]
                p_in = opt.players_in[0]
                hit_str = f"-{opt.hits_taken} pts" if opt.hits_taken > 0 else "Free Transfer"
                print(f"  Option {idx}:")
                print(f"    🔴 OUT : {p_out.web_name} ({p_out.team_short_name} - {p_out.position}) £{p_out.cost_m:.1f}m")
                print(f"    🟢 IN  : {p_in.web_name} ({p_in.team_short_name} - {p_in.position}) £{p_in.cost_m:.1f}m")
                print(f"    📈 Next GW Gain: +{opt.immediate_xp_gain:.2f} xP | Horizon Gain: +{opt.horizon_xp_gain:.2f} xP | Cost: {hit_str}")
                print(f"    ⭐ NET HORIZON GAIN: 📈 +{opt.net_horizon_gain:.2f} xP | Bank Left: £{opt.remaining_bank_m:.1f}m\n")

        # 2. Double Pair Transfers
        if report.double_transfers:
            print("\n2️⃣ TOP DOUBLE TRANSFERS (2-FOR-2 COMBINATORIAL PAIR SWAPS):")
            print("-" * 85)
            for idx, opt in enumerate(report.double_transfers, 1):
                outs_str = " + ".join([f"{p.web_name} (£{p.cost_m:.1f}m)" for p in opt.players_out])
                ins_str = " + ".join([f"{p.web_name} (£{p.cost_m:.1f}m)" for p in opt.players_in])
                hit_str = f"-{opt.hits_taken} pts" if opt.hits_taken > 0 else "All Free Transfers"
                print(f"  Pair Swap {idx}:")
                print(f"    🔴 OUT : {outs_str} (Total: £{opt.total_cost_out_m:.1f}m)")
                print(f"    🟢 IN  : {ins_str} (Total: £{opt.total_cost_in_m:.1f}m)")
                print(f"    📈 Next GW Gain: +{opt.immediate_xp_gain:.2f} xP | Horizon Gain: +{opt.horizon_xp_gain:.2f} xP | Cost: {hit_str}")
                print(f"    ⭐ NET HORIZON GAIN: 📈 +{opt.net_horizon_gain:.2f} xP (Breaks even in GW {opt.break_even_gw}) | Bank Left: £{opt.remaining_bank_m:.1f}m\n")

        # 3. Overall Best Recommendation
        if report.best_overall_recommendation:
            best = report.best_overall_recommendation
            print("=" * 85)
            print(f"👑 OPTIMAL STRATEGIC RECOMMENDATION ({best.transfer_count} Transfer{'s' if best.transfer_count > 1 else ''}):")
            print(f"   {best.rationale}")
            print(f"   Expected Net Horizon Payoff: +{best.net_horizon_gain:.2f} xP")
            print("=" * 85)

    except Exception as e:
        print(f"\n[ERROR] Transfer optimization failed: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
