"""
Understat & FPL Data Fusion Engine.
Fuzzy matches and links Understat players to FPL elements, calculates advanced per-90
metrics (npxG90, xA90, xGChain90, xGBuildup90), and enriches player datasets.
"""
import difflib
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.models.player import UnderstatStats


# Known manual aliases where names differ significantly between FPL and Understat
KNOWN_ALIASES: Dict[str, str] = {
    # FPL web_name / full name -> Understat name
    "gabriel": "Gabriel",
    "bruno fernandes": "Bruno Fernandes",
    "son": "Son Heung-Min",
    "heung-min son": "Son Heung-Min",
    "darwin": "Darwin Núñez",
    "darwin nunez": "Darwin Núñez",
    "luiz diaz": "Luis Díaz",
    "diaz": "Luis Díaz",
    "matheus cunha": "Matheus Cunha",
    "cunha": "Matheus Cunha",
    "rodrigo": "Rodri",
    "rodri": "Rodri",
    "bernardo": "Bernardo Silva",
    "bernardo silva": "Bernardo Silva",
    "rayan": "Rayan Aït-Nouri",
    "ait-nouri": "Rayan Aït-Nouri",
    "muniz": "Rodrigo Muniz",
    "joao pedro": "João Pedro",
    "paqueta": "Lucas Paquetá",
    "lucas paqueta": "Lucas Paquetá",
    "diego carlos": "Diego Carlos",
    "richarlison": "Richarlison",
    "casemiro": "Casemiro",
    "estevao": "Estêvão",
    "joao gomes": "João Gomes",
    "savinho": "Savinho",
    "sávio": "Savinho",
    "savio": "Savinho",
}

# Team name normalization between FPL and Understat
TEAM_NAME_MAP: Dict[str, str] = {
    "arsenal": "Arsenal",
    "aston villa": "Aston Villa",
    "bournemouth": "Bournemouth",
    "brentford": "Brentford",
    "brighton": "Brighton",
    "chelsea": "Chelsea",
    "crystal palace": "Crystal Palace",
    "everton": "Everton",
    "fulham": "Fulham",
    "ipswich": "Ipswich",
    "leicester": "Leicester",
    "liverpool": "Liverpool",
    "man city": "Manchester City",
    "man utd": "Manchester United",
    "manchester city": "Manchester City",
    "manchester united": "Manchester United",
    "newcastle": "Newcastle United",
    "newcastle united": "Newcastle United",
    "nott'm forest": "Nottingham Forest",
    "nottingham forest": "Nottingham Forest",
    "southampton": "Southampton",
    "spurs": "Tottenham",
    "tottenham": "Tottenham",
    "tottenham hotspur": "Tottenham",
    "west ham": "West Ham",
    "west ham united": "West Ham",
    "wolves": "Wolverhampton Wanderers",
    "wolverhampton wanderers": "Wolverhampton Wanderers",
}


def normalize_string(text: str) -> str:
    """Strip accents, lowercase, and remove special characters."""
    if not text:
        return ""
    # Normalize unicode to decompose accents (e.g. é -> e + accent)
    nfkd_form = unicodedata.normalize('NFKD', text)
    only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Lowercase and remove punctuation
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', only_ascii).strip().lower()
    return clean


class UnderstatFusion:
    """Engine for merging Understat metrics into FPL player profiles."""

    def __init__(self, understat_players: Optional[List[Dict[str, Any]]] = None):
        self.understat_players = understat_players or []
        self._parsed_stats_by_id: Dict[int, UnderstatStats] = {}
        self._lookup_by_norm_name: Dict[str, List[Dict[str, Any]]] = {}
        if self.understat_players:
            self._index_understat_data()

    def set_understat_data(self, understat_players: List[Dict[str, Any]]):
        """Set or update Understat players payload."""
        self.understat_players = understat_players
        self._index_understat_data()

    def _index_understat_data(self):
        """Index Understat players by normalized name and team for fast lookup."""
        self._lookup_by_norm_name.clear()
        for p in self.understat_players:
            p_name = p.get("player_name", "")
            norm_name = normalize_string(p_name)
            if norm_name not in self._lookup_by_norm_name:
                self._lookup_by_norm_name[norm_name] = []
            self._lookup_by_norm_name[norm_name].append(p)

    def _parse_understat_metrics(self, u_data: Dict[str, Any]) -> UnderstatStats:
        """Parse raw Understat dictionary into a typed UnderstatStats model."""
        mins = int(u_data.get("time", 0) or 0)
        n90 = mins / 90.0 if mins > 0 else 0.0

        goals = int(u_data.get("goals", 0) or 0)
        xg = float(u_data.get("xG", 0.0) or 0.0)
        npxg = float(u_data.get("npxG", 0.0) or 0.0)
        assists = int(u_data.get("assists", 0) or 0)
        xa = float(u_data.get("xA", 0.0) or 0.0)
        xg_chain = float(u_data.get("xGChain", 0.0) or 0.0)
        xg_buildup = float(u_data.get("xGBuildup", 0.0) or 0.0)
        shots = int(u_data.get("shots", 0) or 0)
        key_passes = int(u_data.get("key_passes", 0) or 0)

        # Per 90 metrics
        npxg90 = round(npxg / n90, 2) if n90 >= 0.5 else 0.0
        xa90 = round(xa / n90, 2) if n90 >= 0.5 else 0.0
        xg90 = round(xg / n90, 2) if n90 >= 0.5 else 0.0
        xg_chain90 = round(xg_chain / n90, 2) if n90 >= 0.5 else 0.0
        xg_buildup90 = round(xg_buildup / n90, 2) if n90 >= 0.5 else 0.0
        shots90 = round(shots / n90, 2) if n90 >= 0.5 else 0.0
        kp90 = round(key_passes / n90, 2) if n90 >= 0.5 else 0.0
        xg_delta = round(goals - xg, 2)

        return UnderstatStats(
            understat_id=int(u_data.get("id")) if u_data.get("id") else None,
            player_name=u_data.get("player_name", ""),
            team_title=u_data.get("team_title", ""),
            minutes=mins,
            goals=goals,
            xG=round(xg, 2),
            npxG=round(npxg, 2),
            assists=assists,
            xA=round(xa, 2),
            xGChain=round(xg_chain, 2),
            xGBuildup=round(xg_buildup, 2),
            shots=shots,
            key_passes=key_passes,
            npxG90=npxg90,
            xa90=xa90,
            xG90=xg90,
            xGChain90=xg_chain90,
            xGBuildup90=xg_buildup90,
            shots90=shots90,
            key_passes90=kp90,
            xg_delta=xg_delta
        )

    def match_player(
        self, 
        web_name: str, 
        first_name: str = "", 
        second_name: str = "", 
        team_name: str = ""
    ) -> Optional[UnderstatStats]:
        """
        Attempt to find the matching Understat player for an FPL player using multi-level matching:
        1. Direct alias match
        2. Exact normalized full name / web_name match (with team validation)
        3. Fuzzy match across all players in the same club
        4. Global fuzzy match
        """
        if not self.understat_players:
            return None

        # Clean strings
        norm_web = normalize_string(web_name)
        norm_full = normalize_string(f"{first_name} {second_name}")
        norm_second = normalize_string(second_name)
        target_team = TEAM_NAME_MAP.get(team_name.lower().strip(), team_name.strip())

        # 1. Check known alias dictionary
        for query in [norm_web, norm_full, norm_second]:
            if query in KNOWN_ALIASES:
                target_alias = normalize_string(KNOWN_ALIASES[query])
                if target_alias in self._lookup_by_norm_name:
                    candidates = self._lookup_by_norm_name[target_alias]
                    # Filter by team if possible
                    for c in candidates:
                        if not target_team or target_team.lower() in c.get("team_title", "").lower():
                            return self._parse_understat_metrics(c)
                    return self._parse_understat_metrics(candidates[0])

        # 2. Check exact normalized full name or web_name
        for candidate_name in [norm_full, norm_web, norm_second]:
            if candidate_name in self._lookup_by_norm_name:
                candidates = self._lookup_by_norm_name[candidate_name]
                for c in candidates:
                    if not target_team or target_team.lower() in c.get("team_title", "").lower():
                        return self._parse_understat_metrics(c)
                return self._parse_understat_metrics(candidates[0])

        # 3. Filter Understat players by team for localized fuzzy matching
        team_candidates = [
            p for p in self.understat_players 
            if not target_team or target_team.lower() in p.get("team_title", "").lower()
        ]
        pool = team_candidates if team_candidates else self.understat_players

        # Find best string match
        best_match = None
        best_score = 0.0

        for candidate in pool:
            cand_name = candidate.get("player_name", "")
            norm_cand = normalize_string(cand_name)

            # Score against full name, web name, and second name
            s1 = difflib.SequenceMatcher(None, norm_full, norm_cand).ratio()
            s2 = difflib.SequenceMatcher(None, norm_web, norm_cand).ratio()
            s3 = difflib.SequenceMatcher(None, norm_second, norm_cand).ratio()
            max_s = max(s1, s2, s3)

            # Substring match bonus
            if norm_web and norm_web in norm_cand:
                max_s = max(max_s, 0.85)
            if norm_second and norm_second in norm_cand:
                max_s = max(max_s, 0.88)

            if max_s > best_score:
                best_score = max_s
                best_match = candidate

        # Acceptance threshold
        if best_match and best_score >= 0.70:
            return self._parse_understat_metrics(best_match)

        return None

    def build_fpl_understat_mapping(
        self, 
        fpl_elements: List[Dict[str, Any]], 
        teams_map: Dict[int, Dict[str, Any]]
    ) -> Dict[int, UnderstatStats]:
        """
        Build a comprehensive dictionary mapping FPL player element IDs to their Understat stats.
        """
        mapping: Dict[int, UnderstatStats] = {}
        for elem in fpl_elements:
            elem_id = elem["id"]
            web_name = elem.get("web_name", "")
            first_name = elem.get("first_name", "")
            second_name = elem.get("second_name", "")
            team_id = elem.get("team", 0)
            team_obj = teams_map.get(team_id, {})
            team_name = team_obj.get("name", "")

            matched = self.match_player(web_name, first_name, second_name, team_name)
            if matched:
                mapping[elem_id] = matched

        return mapping

    def enrich_players_df(
        self, 
        players_df: pd.DataFrame, 
        fpl_elements: List[Dict[str, Any]], 
        teams_map: Dict[int, Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Enrich a Pandas DataFrame of FPL players with Understat metrics columns.
        """
        mapping = self.build_fpl_understat_mapping(fpl_elements, teams_map)
        df = players_df.copy()

        df["understat_npxg"] = df["id"].map(lambda x: mapping[x].npxG if x in mapping else 0.0)
        df["understat_npxg90"] = df["id"].map(lambda x: mapping[x].npxG90 if x in mapping else 0.0)
        df["understat_xa90"] = df["id"].map(lambda x: mapping[x].xA90 if x in mapping else 0.0)
        df["understat_xgchain90"] = df["id"].map(lambda x: mapping[x].xGChain90 if x in mapping else 0.0)
        df["understat_xgbuildup90"] = df["id"].map(lambda x: mapping[x].xGBuildup90 if x in mapping else 0.0)
        df["understat_shots90"] = df["id"].map(lambda x: mapping[x].shots90 if x in mapping else 0.0)
        df["understat_xg_delta"] = df["id"].map(lambda x: mapping[x].xg_delta if x in mapping else 0.0)

        return df
