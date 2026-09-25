"""
Main LangGraph StateGraph Assembly for FPL Agentic AI.
Constructs the multi-agent graph, sets conditional routing, and attaches checkpointer.
"""
from typing import Any, Dict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents.nodes.chip_horizon_node import chip_horizon_node
from src.agents.nodes.lineup_node import lineup_node
from src.agents.nodes.rival_node import rival_node
from src.agents.nodes.scout_node import scout_node
from src.agents.nodes.supervisor import supervisor_node
from src.agents.nodes.synthesis_node import synthesis_node
from src.agents.nodes.transfer_node import transfer_node
from src.agents.state import FPLAgentState


def route_next_step(state: FPLAgentState) -> str:
    """
    Conditional routing function evaluating state['next_node'].
    """
    next_node = state.get("next_node")
    if next_node in ["lineup", "scout", "transfer", "chip", "horizon", "rival", "synthesis"]:
        return next_node
    return "synthesis"


def create_fpl_agent_graph(checkpointer: Any = None):
    """
    Builds and compiles the FPL LangGraph StateGraph.

    Args:
        checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver).

    Returns:
        Compiled LangGraph instance ready for .invoke() or .stream().
    """
    workflow = StateGraph(FPLAgentState)

    # 1. Add all nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("lineup", lineup_node)
    workflow.add_node("scout", scout_node)
    workflow.add_node("transfer", transfer_node)
    workflow.add_node("chip", chip_horizon_node)
    workflow.add_node("horizon", chip_horizon_node)
    workflow.add_node("rival", rival_node)
    workflow.add_node("synthesis", synthesis_node)

    # 2. Add entrypoint
    workflow.add_edge(START, "supervisor")

    # 3. Add conditional routing from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_next_step,
        {
            "lineup": "lineup",
            "scout": "scout",
            "transfer": "transfer",
            "chip": "chip",
            "horizon": "horizon",
            "rival": "rival",
            "synthesis": "synthesis",
        }
    )

    # 4. Worker nodes return to supervisor for next task check
    workflow.add_edge("lineup", "supervisor")
    workflow.add_edge("scout", "supervisor")
    workflow.add_edge("transfer", "supervisor")
    workflow.add_edge("chip", "supervisor")
    workflow.add_edge("horizon", "supervisor")
    workflow.add_edge("rival", "supervisor")

    # 5. Synthesis completes the graph
    workflow.add_edge("synthesis", END)

    memory = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=memory)


# Default compiled graph instance
fpl_agent_graph = create_fpl_agent_graph()
