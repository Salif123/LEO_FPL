"""
Tests for TypeSafe Jev Decision Engine integration, status reporting, and fallback mechanisms.
"""
import os
from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.graph import create_fpl_agent_graph
from src.agents.nodes.jev_scorer import jev_scorer_node
from src.agents.nodes.synthesis_node import synthesis_node
from src.agents.state import FPLAgentState


def test_jev_scorer_fallback_when_no_api_key():
    """Verify jev_scorer gracefully returns 'unavailable' when no OPENROUTER_API_KEY is present."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
        with patch("src.agents.config.AgentConfig.OPENROUTER_API_KEY", None):
            state: FPLAgentState = {
                "messages": [HumanMessage(content="Should I buy Palmer?")],
                "transfer_findings": "Palmer predicted +3.2 xP over Saka."
            }
            result = jev_scorer_node(state)
            assert result["jev_status"] == "unavailable"
            assert result["jev_result"] is None
            assert result["next_node"] == "synthesis"


def test_jev_scorer_mock_online_success():
    """Verify jev_scorer parses structured response and measures latency when Jev responds."""
    mock_payload = b'{"choices": [{"message": {"content": "{\\"verdict\\": \\"Buy Cole Palmer for Bukayo Saka\\", \\"hit_risk\\": \\"Medium\\", \\"urgency_score\\": \\"85%\\", \\"confidence_pct\\": 94.2, \\"primary_action\\": \\"TRANSFER\\", \\"key_metric\\": \\"+3.2 xP net gain\\"}"}}]}'
    
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_payload
    mock_resp.__enter__.return_value = mock_resp

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-mock-test-key"}):
        with patch("src.agents.config.AgentConfig.OPENROUTER_API_KEY", "sk-or-v1-mock-test-key"):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                state: FPLAgentState = {
                    "messages": [HumanMessage(content="Should I buy Palmer?")],
                    "transfer_findings": "Palmer predicted +3.2 xP."
                }
                result = jev_scorer_node(state)
                assert result["jev_status"] == "online"
                assert result["jev_result"] is not None
                assert result["jev_result"]["verdict"] == "Buy Cole Palmer for Bukayo Saka"
                assert result["jev_result"]["hit_risk"] == "Medium"
                assert result["jev_result"]["confidence_pct"] == 94.2
                assert "latency_ms" in result["jev_result"]


def test_synthesis_node_with_jev_online():
    """Verify synthesis_node renders the full online decision card when Jev is active."""
    state: FPLAgentState = {
        "messages": [HumanMessage(content="Should I buy Palmer?")],
        "transfer_findings": "Palmer predicted +3.2 xP.",
        "jev_status": "online",
        "jev_result": {
            "verdict": "Buy Cole Palmer for Bukayo Saka",
            "hit_risk": "Medium",
            "urgency_score": "85%",
            "confidence_pct": 94.2,
            "key_metric": "+3.2 xP net gain",
            "latency_ms": 24.5
        }
    }
    result = synthesis_node(state)
    assert "final_response" in result
    response = result["final_response"]
    assert "TypeSafe Jev Fast Decision Engine" in response
    assert "🟢 Online" in response
    assert "Buy Cole Palmer for Bukayo Saka" in response
    assert "Tactical Coach Advisory" in response


def test_synthesis_node_with_jev_unavailable():
    """Verify synthesis_node renders the 'Not Available' banner when Jev is offline or unconfigured."""
    state: FPLAgentState = {
        "messages": [HumanMessage(content="Should I buy Palmer?")],
        "transfer_findings": "Palmer predicted +3.2 xP.",
        "jev_status": "unavailable",
        "jev_result": None
    }
    result = synthesis_node(state)
    assert "final_response" in result
    response = result["final_response"]
    assert "TypeSafe Jev Fast Decision Engine" in response
    assert "⚠️ **Status: Not Available**" in response
    assert "Tactical Coach Advisory" in response


def test_full_graph_execution_with_jev():
    """Verify the entire LangGraph workflow passes through jev_scorer before synthesis."""
    graph = create_fpl_agent_graph()
    state = {
        "messages": [HumanMessage(content="Scout top transfer targets for manager 1")],
    }
    result = graph.invoke(state, config={"configurable": {"thread_id": "test_jev_flow"}})
    assert result is not None
    assert "jev_status" in result
    assert result["jev_status"] in ["online", "unavailable"]
    assert "final_response" in result
    assert "TypeSafe Jev Fast Decision Engine" in result["final_response"]
