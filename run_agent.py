"""
Interactive CLI Conversational Agent for Fantasy Premier League (FPL).
Powered by LangGraph & the FPL Intelligence Engine.

Usage:
    uv run python run_agent.py
"""
import os
import sys

# Configure UTF-8 stdout for symbols and unicode footballer names
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_core.messages import HumanMessage
from src.agents.graph import create_fpl_agent_graph
from langgraph.checkpoint.memory import MemorySaver


from src.agents.config import detect_llm_provider


def print_banner():
    llm_info = detect_llm_provider()
    print("=" * 75)
    print("⚽  FPL INTELLIGENCE ENGINE — AGENTIC AI ADVISOR (LangGraph)")
    print("=" * 75)
    if llm_info["detected"]:
        print(f"🤖  Active LLM Engine : {llm_info['display']}")
    else:
        print(f"⚠️   Active LLM Engine : {llm_info['display']}")
        print("💡  Tip: Add GROQ_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY to .env for AI synthesis")
    print("-" * 75)
    print("Commands:")
    print("  • Type your question naturally (e.g. 'What transfers should I make for GW6?')")
    print("  • /manager <id>  : Set default manager ID (e.g. /manager 1209336)")
    print("  • /league <id>   : Set default mini-league ID (e.g. /league 314)")
    print("  • /reset         : Clear conversation memory")
    print("  • /exit or /quit : Exit")
    print("=" * 75 + "\n")


def main():
    print_banner()

    checkpointer = MemorySaver()
    graph = create_fpl_agent_graph(checkpointer=checkpointer)

    thread_id = "fpl_user_session_1"
    config = {"configurable": {"thread_id": thread_id}}

    current_manager_id = None
    if os.getenv("DEFAULT_MANAGER_ID"):
        try:
            current_manager_id = int(os.getenv("DEFAULT_MANAGER_ID"))
            print(f"📌 Default Manager ID loaded from environment: {current_manager_id}")
        except ValueError:
            pass

    current_league_id = None
    if os.getenv("DEFAULT_LEAGUE_ID"):
        try:
            current_league_id = int(os.getenv("DEFAULT_LEAGUE_ID"))
            print(f"📌 Default League ID loaded from environment: {current_league_id}")
        except ValueError:
            pass

    print()

    while True:
        try:
            prompt_str = f"FPL Coach"
            if current_manager_id:
                prompt_str += f" [Manager: {current_manager_id}]"
            user_input = input(f"{prompt_str} > ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "/exit", "/quit"]:
                print("👋 Good luck with your Gameweek!")
                break

            if user_input.startswith("/manager"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].isdigit():
                    current_manager_id = int(parts[1])
                    print(f"✓ Target Manager ID set to: {current_manager_id}\n")
                else:
                    print("⚠️ Usage: /manager <manager_id>\n")
                continue

            if user_input.startswith("/league"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].isdigit():
                    current_league_id = int(parts[1])
                    print(f"✓ Target League ID set to: {current_league_id}\n")
                else:
                    print("⚠️ Usage: /league <league_id>\n")
                continue

            if user_input.lower() == "/reset":
                thread_id = f"fpl_user_session_{os.urandom(4).hex()}"
                config = {"configurable": {"thread_id": thread_id}}
                print("✓ Conversation memory reset.\n")
                continue

            # Run LangGraph Agent
            print("\n⏳ Analyzing data across specialist nodes...")

            initial_state = {
                "messages": [HumanMessage(content=user_input)],
                "manager_id": current_manager_id,
                "league_id": current_league_id,
            }

            result = graph.invoke(initial_state, config=config)

            print("\n" + "-" * 75)
            final_res = result.get("final_response") or result["messages"][-1].content
            print(final_res)
            print("-" * 75 + "\n")

            # Update manager/league if extracted by supervisor
            if result.get("manager_id"):
                current_manager_id = result["manager_id"]
            if result.get("league_id"):
                current_league_id = result["league_id"]

        except KeyboardInterrupt:
            print("\n👋 Good luck with your Gameweek!")
            break
        except Exception as e:
            print(f"\n❌ Error during execution: {e}\n")


if __name__ == "__main__":
    main()
