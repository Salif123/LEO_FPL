"""
Integration tests for FPL LangGraph StateGraph Execution and Multi-Turn Memory.
"""
import pytest
from langchain_core.messages import HumanMessage
from src.agents.graph import create_fpl_agent_graph
from langgraph.checkpoint.memory import MemorySaver


def test_agent_graph_creation():
    """Verify graph compiles cleanly."""
    graph = create_fpl_agent_graph()
    assert graph is not None


def test_agent_graph_transfer_intent():
    """Test graph execution for a transfer and hit query."""
    memory = MemorySaver()
    graph = create_fpl_agent_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "test_thread_1"}}

    state = {
        "messages": [HumanMessage(content="What transfers should I make? Manager 1")],
    }
    result = graph.invoke(state, config=config)
    assert result is not None
    assert "messages" in result
    assert len(result["messages"]) >= 2
    assert result.get("manager_id") == 1
    assert "transfer" in result.get("completed_tasks", [])


def test_agent_graph_scout_intent():
    """Test graph execution for scouting and Understat query."""
    memory = MemorySaver()
    graph = create_fpl_agent_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "test_thread_2"}}

    state = {
        "messages": [HumanMessage(content="Scout top underperforming players due a goal and check Haaland stats")],
    }
    result = graph.invoke(state, config=config)
    assert result is not None
    assert "scout" in result.get("completed_tasks", [])
    assert "scout_findings" in result


def test_agent_graph_chip_intent():
    """Test graph execution for chip valuation and horizon."""
    memory = MemorySaver()
    graph = create_fpl_agent_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "test_thread_3"}}

    state = {
        "messages": [HumanMessage(content="Should I use my Wildcard or Free Hit? Manager 1")],
    }
    result = graph.invoke(state, config=config)
    assert result is not None
    assert "chip" in result.get("completed_tasks", [])
    assert result.get("chip_findings") is not None


def test_agent_graph_multi_turn_memory():
    """Test multi-turn context retention across conversation turns."""
    memory = MemorySaver()
    graph = create_fpl_agent_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "multi_turn_session"}}

    # Turn 1: Introduce manager ID
    turn1 = graph.invoke(
        {"messages": [HumanMessage(content="Hello, analyze my squad for manager 1")]},
        config=config
    )
    assert turn1.get("manager_id") == 1

    # Turn 2: Follow up without repeating manager ID
    turn2 = graph.invoke(
        {"messages": [HumanMessage(content="What about transfer moves?")]},
        config=config
    )
    assert turn2.get("manager_id") == 1
    assert "transfer" in turn2.get("completed_tasks", [])
