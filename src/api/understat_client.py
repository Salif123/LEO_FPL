"""
Understat xG and Advanced Statistics Client with TTL caching.
Provides access to shot maps, xGChain, xGBuildup, and deep statistical data.
"""
import json
import re
from typing import Any, Dict, List, Optional
from src.api.base_client import BaseClient
from src.cache.cache_manager import CacheManager, get_cache
from src.config import UnderstatConfig


class UnderstatClient:
    """Client for fetching advanced xG data and shot maps from Understat."""

    def __init__(self, client: Optional[BaseClient] = None, cache: Optional[CacheManager] = None):
        self.client = client or BaseClient(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            timeout=15
        )
        self.cache = cache if cache is not None else get_cache()

    def _extract_script_json(self, html_text: str, variable_name: str) -> Any:
        """
        Helper method to extract and decode JSON encoded inside JavaScript variables
        e.g., var playersData = JSON.parse('...');
        """
        pattern = rf"var\s+{variable_name}\s*=\s*JSON\.parse\('([^']+)'\)"
        match = re.search(pattern, html_text)
        if not match:
            # Fallback for double-quoted strings
            pattern_dq = rf'var\s+{variable_name}\s*=\s*JSON\.parse\("([^"]+)"\)'
            match = re.search(pattern_dq, html_text)
            
        if not match:
            return None

        raw_hex_or_string = match.group(1)
        # Decode hex escape sequences e.g. \x7B -> {
        try:
            decoded_str = raw_hex_or_string.encode('utf-8').decode('unicode_escape')
            return json.loads(decoded_str)
        except Exception:
            return None

    def get_league_players(self, season: Optional[str] = None, use_cache: bool = True, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all Premier League players with advanced Understat stats:
        - xG, xA, npxG (non-penalty xG), xG90, xA90
        - xGChain (xG of every possession player was involved in)
        - xGBuildup (xG of possessions player was involved in excluding shots and key passes)
        :param season: e.g. '2024' or None for current
        """
        cache_id = f"epl_{season or 'current'}"
        if use_cache and not force_refresh:
            cached = self.cache.get("understat", identifier=cache_id)
            if cached:
                return cached

        url = UnderstatConfig.LEAGUE_EPL_URL
        if season:
            url = f"{url}/{season}"
            
        html = self.client.get(url)
        if isinstance(html, str):
            data = self._extract_script_json(html, "playersData") or []
            if use_cache and data:
                self.cache.set("understat", data, identifier=cache_id)
            return data
        return []

    def get_match_shots(self, match_id: int, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch shot-by-shot xG map for a specific match:
        - Coordinates (X, Y) of every shot
        - xG value, shot type (head, right foot, left foot)
        - Situation (Open Play, From Corner, Set Piece, Penalty)
        - Result (Goal, SavedShot, MissedShots, BlockedShot)
        - Player and assist info
        """
        cache_id = f"match_shots_{match_id}"
        if use_cache and not force_refresh:
            cached = self.cache.get("understat", identifier=cache_id)
            if cached:
                return cached

        url = UnderstatConfig.MATCH_URL.format(match_id=match_id)
        html = self.client.get(url)
        if isinstance(html, str):
            data = self._extract_script_json(html, "shotsData") or {}
            if use_cache and data:
                self.cache.set("understat", data, identifier=cache_id)
            return data
        return {}

    def close(self):
        """Close the underlying HTTP session."""
        self.client.close()
