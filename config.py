import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

# FPL API Endpoints
FPL_BASE_URL = "https://fantasy.premierleague.com/api"
FPL_BOOTSTRAP_URL = f"{FPL_BASE_URL}/bootstrap-static/"
FPL_FIXTURES_URL = f"{FPL_BASE_URL}/fixtures/"
FPL_ELEMENT_SUMMARY_URL = f"{FPL_BASE_URL}/element-summary/"  # append {player_id}/
FPL_ENTRY_URL = f"{FPL_BASE_URL}/entry/"  # append {team_id}/
FPL_ENTRY_PICKS_URL = f"{FPL_BASE_URL}/entry/{{team_id}}/event/{{gameweek}}/picks/"

# Cache Settings
CACHE_DIR = BASE_DIR / "data" / "cache"
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default

# User Agent for FPL API
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
