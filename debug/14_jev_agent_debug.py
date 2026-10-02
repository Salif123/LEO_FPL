r"""
Debug Script: Jev & Hybrid Dual-Engine Agent Runner
Run via: uv run python debug/14_jev_agent_debug.py
"""
import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage
from src.agents.config import detect_llm_provider, AgentConfig
from src.agents.graph import create_fpl_agent_graph


def main():
    print("=" * 70)
    print("🤖 FPL AGENTIC ENGINE - HYBRID JEV & LLM DEBUG CONSOLE")
    print("=" * 70)

    # 1. Inspect Environment & Providers
    provider_info = detect_llm_provider()
    print("\n[1] LLM Provider Status:")
    print(f"    - Synthesis Engine: {provider_info.get('display')}")
    print(f"    - Synthesis Model : {provider_info.get('model')}")
    
    openrouter_key = AgentConfig.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        masked_key = openrouter_key[:8] + "..." + openrouter_key[-4:] if len(openrouter_key) > 12 else "LOADED"
        print(f"    - Jev Engine Key  : ✅ {masked_key}")
        print(f"    - Jev Model       : {AgentConfig.JEV_MODEL or os.getenv('JEV_MODEL', 'typesafe/jev')}")
    else:
        print("    - Jev Engine Key  : ⚠️ None found (Graceful Fallback Mode will activate)")

    # 2. Compile Graph
    print("\n[2] Compiling LangGraph...")
    graph = create_fpl_agent_graph()
    print("    ✅ Graph compiled successfully!")

    # 3. Test Queries
    queries = [
        "Should I take a -4 point hit to buy Cole Palmer for Bukayo Saka? Manager 1",
        "Who should I captain this gameweek and check Understat underlying xG for Haaland?",
    ]

    print("\n[3] Executing Sample Debug Queries:")
    for idx, query in enumerate(queries, 1):
        print("\n" + "-" * 70)
        print(f"🔍 [Query {idx}]: \"{query}\"")
        print("-" * 70)

        state_input = {"messages": [HumanMessage(content=query)]}
        thread_config = {"configurable": {"thread_id": f"debug_thread_{idx}"}}
        
        # Step through nodes live to observe graph routing
        print("  🔄 Executing Graph Nodes:")
        final_response_text = None
        for event in graph.stream(state_input, config=thread_config, stream_mode="updates"):
            for node_name, node_output in event.items():
                print(f"     ➔ Node Finished: [{node_name}]")
                if node_name == "jev_scorer":
                    status = node_output.get("jev_status")
                    result = node_output.get("jev_result")
                    print(f"        • Jev Status: {status}")
                    if result:
                        print(f"        • Jev Latency: {result.get('latency_ms')}ms")
                        print(f"        • Jev Verdict: {result.get('verdict')}")
                        print(f"        • Jev Hit Risk: {result.get('hit_risk')}")
                        print(f"        • Jev Confidence: {result.get('confidence_pct')}%")
                if node_name == "synthesis":
                    final_response_text = node_output.get("final_response")

        print("\n  📋 Final Response Output:")
        print("=" * 70)
        print(final_response_text or "No response generated.")
        print("=" * 70)


if __name__ == "__main__":
    main()
