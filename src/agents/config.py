"""
LLM Configuration, Detection, and Provider Factory for FPL Agentic Engine.
Supports Groq, Google Gemini, OpenAI, and Anthropic.
"""
import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()


class AgentConfig:
    """Agent configuration settings."""
    DEFAULT_PROVIDER = os.getenv("FPL_LLM_PROVIDER", "").lower()
    DEFAULT_MODEL = os.getenv("FPL_AGENT_MODEL", "")
    DEFAULT_TEMPERATURE = float(os.getenv("FPL_AGENT_TEMPERATURE", "0.1"))
    MAX_ITERATIONS = int(os.getenv("FPL_AGENT_MAX_ITERATIONS", "10"))
    
    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    if GROQ_API_KEY:
        print("✅ GROQ_API_KEY loaded successfully!")
    else:
        print("❌ GROQ_API_KEY not found!")
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def detect_llm_provider() -> Dict[str, Any]:
    """
    Detects which LLM provider and model are currently configured in the environment / .env file.
    
    Returns:
        Dictionary containing detected provider name, model, active status, and human-friendly badge.
    """
    prov = AgentConfig.DEFAULT_PROVIDER
    
    # 1. Check Groq
    if prov == "groq" or (AgentConfig.GROQ_API_KEY and not prov):
        model = AgentConfig.DEFAULT_MODEL or "openai/gpt-oss-120b"
        return {
            "detected": True,
            "provider": "Groq",
            "model": model,
            "display": f"Groq ({model}) 🚀"
        }
        
    # 2. Check Google Gemini
    if prov in ["gemini", "google"] or (AgentConfig.GOOGLE_API_KEY and not prov):
        model = AgentConfig.DEFAULT_MODEL or "gemini-2.0-flash"
        return {
            "detected": True,
            "provider": "Google Gemini",
            "model": model,
            "display": f"Google Gemini ({model}) ⚡"
        }
        
    # 3. Check OpenAI
    if prov == "openai" or (AgentConfig.OPENAI_API_KEY and not prov):
        model = AgentConfig.DEFAULT_MODEL or "gpt-4o-mini"
        return {
            "detected": True,
            "provider": "OpenAI",
            "model": model,
            "display": f"OpenAI ({model}) 🧠"
        }
        
    # 4. Check Anthropic
    if prov == "anthropic" or (AgentConfig.ANTHROPIC_API_KEY and not prov):
        model = AgentConfig.DEFAULT_MODEL or "claude-3-5-sonnet-latest"
        return {
            "detected": True,
            "provider": "Anthropic",
            "model": model,
            "display": f"Anthropic ({model}) 💡"
        }

    # 5. Offline Fallback Mode
    return {
        "detected": False,
        "provider": "None",
        "model": "Offline Deterministic Solver",
        "display": "Offline Fallback Mode (No API key found in .env) ⚠️"
    }


def get_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    provider: Optional[str] = None
) -> BaseChatModel:
    """
    Factory function returning an initialized LangChain ChatModel instance based on detected provider.
    """
    llm_info = detect_llm_provider()
    target_provider = (provider or llm_info["provider"]).lower()
    target_temp = temperature if temperature is not None else AgentConfig.DEFAULT_TEMPERATURE
    target_model = model or AgentConfig.DEFAULT_MODEL or llm_info["model"]

    # 1. Groq Provider
    if "groq" in target_provider or AgentConfig.GROQ_API_KEY:
        try:
            from langchain_groq import ChatGroq
            if not AgentConfig.GROQ_API_KEY:
                raise ValueError("Missing GROQ_API_KEY in environment or .env file.")
            return ChatGroq(
                model=target_model or "openai/gpt-oss-120b",
                temperature=target_temp,
                api_key=AgentConfig.GROQ_API_KEY,
            )
        except ImportError:
            pass

    # 2. Google Gemini Provider
    if "gemini" in target_provider or "google" in target_provider or AgentConfig.GOOGLE_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            if not AgentConfig.GOOGLE_API_KEY:
                raise ValueError("Missing GEMINI_API_KEY or GOOGLE_API_KEY in environment or .env file.")
            return ChatGoogleGenerativeAI(
                model=target_model if "gemini" in target_model else "gemini-2.0-flash",
                temperature=target_temp,
                google_api_key=AgentConfig.GOOGLE_API_KEY,
            )
        except ImportError:
            pass

    # 3. OpenAI Provider
    if "openai" in target_provider or AgentConfig.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            if not AgentConfig.OPENAI_API_KEY:
                raise ValueError("Missing OPENAI_API_KEY in environment or .env file.")
            return ChatOpenAI(
                model=target_model if "gpt" in target_model else "gpt-4o-mini",
                temperature=target_temp,
                api_key=AgentConfig.OPENAI_API_KEY,
            )
        except ImportError:
            pass

    raise ValueError(
        "No active LLM provider detected. Please add GROQ_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY to your .env file."
    )
