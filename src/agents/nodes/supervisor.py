"""
Supervisor Node: Interprets user queries, extracts context, plans required tasks, and routes between nodes.
"""
import os
import re
from typing import Any, Dict, List
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.state import FPLAgentState


def _extract_ids_from_text(text: str) -> Dict[str, Any]:
    """Extract manager_id or league_id from user prompt."""
    results = {}
    
    # Manager ID pattern: "manager 1209336", "team 1209336", "id 1209336", "manager_id=1209336"
    m_match = re.search(r'(?:manager|team|my id|entry)[\s:=#]*([0-9]{1,8})', text, re.IGNORECASE)
    if m_match:
        results["manager_id"] = int(m_match.group(1))
        
    # League ID pattern: "league 314", "mini league 12345"
    l_match = re.search(r'(?:league|mini-league|minileague)[\s:=#]*([0-9]{1,8})', text, re.IGNORECASE)
    if l_match:
        results["league_id"] = int(l_match.group(1))
        
    return results


def supervisor_node(state: FPLAgentState) -> Dict[str, Any]:
    """
    Evaluates conversation state, extracts IDs, initializes required tasks,
    and determines the next specialist node to execute.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"next_node": "synthesis"}

    last_message = messages[-1]
    user_query = last_message.content if isinstance(last_message, (HumanMessage, AIMessage)) else str(last_message)
    
    # Extract IDs if not already set in state
    extracted = _extract_ids_from_text(user_query)
    manager_id = state.get("manager_id") or extracted.get("manager_id")
    if not manager_id and os.getenv("DEFAULT_MANAGER_ID"):
        try:
            manager_id = int(os.getenv("DEFAULT_MANAGER_ID"))
        except ValueError:
            pass
            
    league_id = state.get("league_id") or extracted.get("league_id")
    if not league_id and os.getenv("DEFAULT_LEAGUE_ID"):
        try:
            league_id = int(os.getenv("DEFAULT_LEAGUE_ID"))
        except ValueError:
            pass

    # Determine tasks if not yet initialized
    completed = state.get("completed_tasks", []) or []
    required = state.get("required_tasks")

    if required is None:
        required = []
        q_lower = user_query.lower()

        # Route matching heuristics
        wants_transfer = any(k in q_lower for k in ["transfer", "swap", "sell", "buy", "bring in", "hit", "-4", "-8", "replace"])
        wants_scout = any(k in q_lower for k in ["xg", "xa", "npxg", "understat", "stats", "unlucky", "form", "due a goal", "scout", "metrics"])
        wants_chip = any(k in q_lower for k in ["chip", "wildcard", "free hit", "bench boost", "triple captain", "bb", "tc", "fh", "wc", "dgw", "bgw", "double"])
        wants_horizon = any(k in q_lower for k in ["horizon", "next 5", "next 3", "upcoming fixtures", "fixture swing", "schedule", "run"])
        wants_rival = any(k in q_lower for k in ["league", "rival", "effective ownership", "eo", "overlap", "differential", "rank", "leader"])
        wants_lineup = any(k in q_lower for k in ["lineup", "starting xi", "captain", "vice captain", "bench", "formation", "who to start", "pick"])

        if wants_transfer:
            required.append("transfer")
        if wants_scout:
            required.append("scout")
        if wants_chip:
            required.append("chip")
        if wants_horizon and "chip" not in required:
            required.append("horizon")
        if wants_rival:
            required.append("rival")
        if wants_lineup and "transfer" not in required:
            required.append("lineup")

        # Default to lineup + transfer briefing if general question asked
        if not required:
            if manager_id:
                required = ["lineup", "transfer"]
            else:
                required = ["scout"]

    # Pick next pending task
    pending = [t for t in required if t not in completed]
    
    if pending:
        next_task = pending[0]
        return {
            "manager_id": manager_id,
            "league_id": league_id,
            "required_tasks": required,
            "completed_tasks": completed,
            "next_node": next_task,
            "iteration_count": state.get("iteration_count", 0) + 1
        }
    
    # All tasks done -> synthesize final answer
    return {
        "manager_id": manager_id,
        "league_id": league_id,
        "required_tasks": required,
        "completed_tasks": completed,
        "next_node": "synthesis",
        "iteration_count": state.get("iteration_count", 0) + 1
    }
