import requests
from typing import Any, Optional, Dict, List
from config import (
    FPL_BOOTSTRAP_URL,
    FPL_FIXTURES_URL,
    FPL_ELEMENT_SUMMARY_URL,
    FPL_ENTRY_URL,
    FPL_ENTRY_PICKS_URL,
    HTTP_HEADERS,
)
from src.api.cache_manager import CacheManager

class FPLClient:
    """Client for fetching data from the official free Fantasy Premier League REST API."""
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()
        self.session = requests.Session()
        self.session.headers.update(HTTP_HEADERS)

    def _get(self, url: str, cache_key: str, ttl: Optional[int] = None) -> Dict[str, Any]:
        """Fetch JSON data from URL with caching."""
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.cache.set(cache_key, data)
            return data
        except Exception as e:
            # If request fails, attempt to return stale cache if available
            stale_cache = self.cache.get(cache_key)
            if stale_cache is not None:
                return stale_cache
            raise ConnectionError(f"Failed to fetch data from {url}: {e}")

    def get_bootstrap_static(self) -> Dict[str, Any]:
        """Fetch all core FPL data (players, teams, gameweeks, element_types)."""
        return self._get(FPL_BOOTSTRAP_URL, "bootstrap_static")

    def get_fixtures(self) -> List[Dict[str, Any]]:
        """Fetch all season fixtures with Home/Away difficulty ratings."""
        return self._get(FPL_FIXTURES_URL, "fixtures")

    def get_player_summary(self, player_id: int) -> Dict[str, Any]:
        """Fetch detailed match history and upcoming fixtures for a specific player."""
        url = f"{FPL_ELEMENT_SUMMARY_URL}{player_id}/"
        return self._get(url, f"player_summary_{player_id}")

    def get_manager_entry(self, team_id: int) -> Dict[str, Any]:
        """Fetch FPL manager team info (name, overall points, overall rank)."""
        url = f"{FPL_ENTRY_URL}{team_id}/"
        return self._get(url, f"manager_entry_{team_id}")

    def get_manager_picks(self, team_id: int, gameweek: int) -> Dict[str, Any]:
        """Fetch manager squad picks, bank balance, chips played, and transfers for a gameweek."""
        url = FPL_ENTRY_PICKS_URL.format(team_id=team_id, gameweek=gameweek)
        return self._get(url, f"manager_picks_{team_id}_gw{gameweek}")

    def get_current_gameweek(self) -> int:
        """Helper to get the active/upcoming gameweek ID."""
        bootstrap = self.get_bootstrap_static()
        events = bootstrap.get("events", [])
        for event in events:
            if event.get("is_current") or event.get("is_next"):
                return event.get("id", 1)
        return 1
