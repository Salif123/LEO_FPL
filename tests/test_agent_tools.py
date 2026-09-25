"""
Unit tests for LangChain FPL Agent Tools.
"""
import pytest
from src.agents.tools import (
    ALL_FPL_TOOLS,
    get_manager_squad_info,
    get_optimal_lineup_and_captain,
    optimize_squad_transfers,
    get_multi_gameweek_horizon,
    evaluate_chip_strategy,
    analyze_mini_league_and_rivals,
    get_understat_player_metrics,
    get_top_understat_underperformers,
)


def test_tool_definitions():
    """Verify that all tools have valid names, descriptions, and schemas."""
    assert len(ALL_FPL_TOOLS) == 8
    for tool in ALL_FPL_TOOLS:
        assert hasattr(tool, "name")
        assert len(tool.name) > 0
        assert hasattr(tool, "description")
        assert len(tool.description) > 0
        assert hasattr(tool, "args_schema")


def test_understat_player_metrics_tool():
    """Test get_understat_player_metrics tool invocation."""
    result = get_understat_player_metrics.invoke({"player_name": "Haaland"})
    assert isinstance(result, dict)
    assert "found" in result
    if result["found"]:
        assert result["goals"] >= 0
        assert "per_90_metrics" in result
        assert "npxG90" in result["per_90_metrics"]


def test_understat_underperformers_tool():
    """Test get_top_understat_underperformers tool invocation."""
    result = get_top_understat_underperformers.invoke({"limit": 5})
    assert isinstance(result, list)
    assert len(result) <= 5
    if result:
        assert "player" in result[0]
        assert "xg_delta_unlucky" in result[0]


def test_manager_squad_info_tool():
    """Test get_manager_squad_info tool invocation."""
    result = get_manager_squad_info.invoke({"manager_id": 1})
    assert isinstance(result, dict)
    assert "manager_name" in result
    assert "starting_xi" in result
    assert len(result["starting_xi"]) == 11
    assert len(result["bench"]) == 4


def test_optimal_lineup_tool():
    """Test get_optimal_lineup_and_captain tool invocation."""
    result = get_optimal_lineup_and_captain.invoke({"manager_id": 1})
    assert isinstance(result, dict)
    assert "optimal_formation" in result
    assert "recommended_captain" in result
    assert len(result["starting_xi"]) == 11


def test_chip_strategy_tool():
    """Test evaluate_chip_strategy tool invocation."""
    result = evaluate_chip_strategy.invoke({"manager_id": 1})
    assert isinstance(result, dict)
    assert "chips_remaining" in result
    assert "recommended_chip_roadmap" in result
