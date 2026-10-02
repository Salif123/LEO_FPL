"""
Unit tests for the FPL MCP Server tools and prompts registration.
"""
import pytest
from mcp_server import mcp


def test_mcp_initialization():
    """Verify that FastMCP initialized with correct metadata."""
    assert mcp.name == "FPL Intelligence Engine"


def test_mcp_registered_tools():
    """Verify that all 7 primary tools and understat tools are registered."""
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    expected_tools = [
        "get_squad",
        "get_optimal_lineup",
        "optimize_transfers",
        "get_horizon_projections",
        "evaluate_chips",
        "analyze_mini_league",
        "get_understat_metrics",
        "get_unlucky_underperformers",
    ]
    for exp in expected_tools:
        assert exp in tool_names, f"Expected tool '{exp}' not found in MCP server"


def test_mcp_registered_prompts():
    """Verify MCP prompt templates are registered."""
    prompt_names = [p.name for p in mcp._prompt_manager.list_prompts()]
    assert "gameweek_prep_briefing" in prompt_names
    assert "rival_differentials_briefing" in prompt_names
