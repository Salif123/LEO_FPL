"""
Configuration module for FPL and football statistics APIs.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class FPLConfig:
    """Official FPL API endpoints and constants."""
    BASE_URL = "https://fantasy.premierleague.com/api"
    
    BOOTSTRAP_STATIC_URL = f"{BASE_URL}/bootstrap-static/"
    ELEMENT_SUMMARY_URL = f"{BASE_URL}/element-summary/{{player_id}}/"
    FIXTURES_URL = f"{BASE_URL}/fixtures/"
    EVENT_LIVE_URL = f"{BASE_URL}/event/{{event_id}}/live/"
    
    # Manager & Team endpoints
    MANAGER_ENTRY_URL = f"{BASE_URL}/entry/{{manager_id}}/"
    MANAGER_PICKS_URL = f"{BASE_URL}/entry/{{manager_id}}/event/{{event_id}}/picks/"
    MANAGER_HISTORY_URL = f"{BASE_URL}/entry/{{manager_id}}/history/"
    MANAGER_TRANSFERS_URL = f"{BASE_URL}/entry/{{manager_id}}/transfers/"
    MY_TEAM_URL = f"{BASE_URL}/my-team/{{manager_id}}/"
    
    # Leagues
    CLASSIC_LEAGUE_URL = f"{BASE_URL}/leagues-classic/{{league_id}}/standings/"
    H2H_LEAGUE_URL = f"{BASE_URL}/leagues-h2h/{{league_id}}/standings/"
    
    # Default Request Settings
    DEFAULT_TIMEOUT_SECONDS = 15
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # Environment variables
    DEFAULT_MANAGER_ID = os.getenv("DEFAULT_MANAGER_ID", None)
    DEFAULT_LEAGUE_ID = os.getenv("DEFAULT_LEAGUE_ID", None)
    FPL_COOKIE = os.getenv("FPL_COOKIE", None)


class UnderstatConfig:
    """Understat xG endpoints and constants."""
    BASE_URL = "https://understat.com"
    LEAGUE_EPL_URL = f"{BASE_URL}/league/EPL"
    PLAYER_URL = f"{BASE_URL}/player/{{player_id}}"
    MATCH_URL = f"{BASE_URL}/match/{{match_id}}"
