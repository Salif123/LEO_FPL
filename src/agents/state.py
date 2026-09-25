"""
LangGraph state definitions for the FPL Agentic AI Engine.
"""
from typing import Annotated, Any, Dict, List, Optional, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class FPLAgentState(TypedDict, total=False):
    """
    Unified state passed across all LangGraph nodes (Supervisor, Scout, Transfer, Chip, Rival, Synthesizer).
    """
    # 1. Core conversation history (appends new messages automatically)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # 2. Manager and Environment Context
    manager_id: Optional[int]
    league_id: Optional[int]
    target_gameweek: Optional[int]
    
    # 3. Squad & Financial Context (hydrated on demand)
    squad_summary: Optional[Dict[str, Any]]
    chips_remaining: Optional[List[str]]
    chips_used: Optional[Dict[str, int]]
    bank_m: Optional[float]
    
    # 4. Specialist Node Findings (intermediate analysis artifacts)
    scout_findings: Optional[str]
    transfer_findings: Optional[str]
    horizon_findings: Optional[str]
    chip_findings: Optional[str]
    rival_findings: Optional[str]
    
    # 5. Routing and Orchestration State
    next_node: Optional[str]
    required_tasks: Optional[List[str]]
    completed_tasks: Optional[List[str]]
    iteration_count: int
    final_response: Optional[str]
