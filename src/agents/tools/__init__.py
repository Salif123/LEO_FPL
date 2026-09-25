"""
Central registry exporting all FPL and Understat LangChain tools.
"""
from src.agents.tools.squad_tools import (
    get_manager_squad_info,
    get_optimal_lineup_and_captain,
)
from src.agents.tools.transfer_tools import (
    optimize_squad_transfers,
)
from src.agents.tools.horizon_tools import (
    get_multi_gameweek_horizon,
)
from src.agents.tools.chip_tools import (
    evaluate_chip_strategy,
)
from src.agents.tools.league_tools import (
    analyze_mini_league_and_rivals,
)
from src.agents.tools.understat_tools import (
    get_understat_player_metrics,
    get_top_understat_underperformers,
)

# Export full catalog of tools
ALL_FPL_TOOLS = [
    get_manager_squad_info,
    get_optimal_lineup_and_captain,
    optimize_squad_transfers,
    get_multi_gameweek_horizon,
    evaluate_chip_strategy,
    analyze_mini_league_and_rivals,
    get_understat_player_metrics,
    get_top_understat_underperformers,
]

__all__ = [
    "ALL_FPL_TOOLS",
    "get_manager_squad_info",
    "get_optimal_lineup_and_captain",
    "optimize_squad_transfers",
    "get_multi_gameweek_horizon",
    "evaluate_chip_strategy",
    "analyze_mini_league_and_rivals",
    "get_understat_player_metrics",
    "get_top_understat_underperformers",
]
