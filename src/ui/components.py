import streamlit as st
from typing import List, Dict, Any
from src.engine.models import Player, Position, FixtureRun, EngineVerdict, VerdictEnum

# Premier League Theme Custom CSS
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background-color: #0d0a1a;
        color: #f8f9fa;
    }
    
    .leo-header {
        background: linear-gradient(135deg, #37003c 0%, #170020 50%, #00ff87 180%);
        padding: 24px;
        border-radius: 16px;
        border: 1px solid rgba(0, 255, 135, 0.2);
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    
    .fdr-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
        margin-right: 4px;
        text-align: center;
    }
    .fdr-1, .fdr-2 { background-color: #00ff87; color: #000; }
    .fdr-3 { background-color: #e6e6e6; color: #333; }
    .fdr-4 { background-color: #ff2882; color: #fff; }
    .fdr-5 { background-color: #8b0000; color: #fff; }
    
    .pitch-container {
        background: radial-gradient(circle at center, #1b4d2e 0%, #0d2616 100%);
        border: 2px solid #2d7a48;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: inset 0 0 40px rgba(0,0,0,0.5);
    }
    
    .player-card {
        background: rgba(255, 255, 255, 0.07);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 12px;
        padding: 10px;
        text-align: center;
        transition: transform 0.2s, border-color 0.2s;
    }
    .player-card:hover {
        transform: translateY(-3px);
        border-color: #00ff87;
    }
    
    .verdict-card {
        background: rgba(55, 0, 60, 0.6);
        border: 1px solid #00ff87;
        border-radius: 14px;
        padding: 20px;
        margin-top: 15px;
        box-shadow: 0 4px 20px rgba(0, 255, 135, 0.15);
    }
</style>
"""

def render_fdr_badge(fixture: FixtureRun) -> str:
    """Returns HTML for a color-coded FDR badge."""
    loc = "H" if fixture.is_home else "A"
    diff = fixture.difficulty
    return f'<span class="fdr-badge fdr-{diff}">{fixture.opponent_short} ({loc})</span>'

def render_fixtures_html(fixtures: List[FixtureRun]) -> str:
    """Renders a series of colored FDR badges."""
    return "".join([render_fdr_badge(f) for f in fixtures])

def render_verdict_card(leo_text: str):
    """Renders Leo's formatted response in a tactical card container."""
    st.markdown(f'<div class="verdict-card">{st.markdown(leo_text)}</div>', unsafe_allow_html=True)
