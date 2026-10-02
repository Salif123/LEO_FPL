"""
Debug Script: Cache Performance & Latency Benchmark
Compares Cold Network Request latency against Warm Cache retrieval latency across all core endpoints.

Run:
    python debug/12_cache_benchmark.py
"""
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.fpl_client import FPLClient
from src.api.understat_client import UnderstatClient
from src.cache.cache_manager import get_cache


def benchmark_call(label: str, func, *args, **kwargs) -> tuple[float, any]:
    """Execute a function and measure elapsed time in milliseconds."""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms, result


def main():
    print("=" * 80)
    print("⚡  DEBUG: Cache Performance & Latency Benchmark")
    print("=" * 80)

    cache = get_cache()
    fpl_client = FPLClient(cache=cache)
    understat_client = UnderstatClient(cache=cache)

    print("\n1. Clearing existing cache to ensure cold benchmark...")
    deleted = cache.clear()
    print(f"   ✓ Cleared {deleted} cached files.\n")

    endpoints = [
        ("FPL Bootstrap Static", lambda: fpl_client.get_bootstrap_static(use_cache=True)),
        ("FPL Premier League Fixtures", lambda: fpl_client.get_fixtures(use_cache=True)),
        ("FPL Element Summary (Haaland #355)", lambda: fpl_client.get_element_summary(355, use_cache=True)),
        ("FPL Manager Entry (#1)", lambda: fpl_client.get_manager(1, use_cache=True)),
        ("Understat Premier League", lambda: understat_client.get_league_players(use_cache=True)),
    ]

    print(f"{'Endpoint':<35} | {'Cold (Network)':<15} | {'Warm (Cache)':<14} | {'Speedup'}")
    print("-" * 80)

    for name, call_fn in endpoints:
        # Force fresh network call (Cold)
        cache.clear()
        cold_time, _ = benchmark_call(name, call_fn)

        # Retrieve from cache (Warm)
        warm_time, _ = benchmark_call(name, call_fn)

        speedup = f"{cold_time / warm_time:.0f}x faster" if warm_time > 0 else "Instant"
        print(f"{name:<35} | {cold_time:>8.1f} ms     | {warm_time:>8.2f} ms    | {speedup}")

    print("-" * 80)
    print("✓ Cache benchmark complete.")

    fpl_client.close()
    understat_client.close()


if __name__ == "__main__":
    main()
