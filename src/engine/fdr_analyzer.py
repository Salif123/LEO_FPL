from typing import List, Dict, Any
from src.engine.models import FixtureRun

class FDRAnalyzer:
    """Analyzes upcoming fixtures with Home/Away difficulty ratings."""
    def __init__(self, fixtures_raw: List[Dict[str, Any]], teams_map: Dict[int, str]):
        self.fixtures_raw = fixtures_raw
        self.teams_map = teams_map  # team_id -> team_short_name

    def get_upcoming_fixtures_for_team(
        self, team_id: int, current_gw: int, horizon: int = 5
    ) -> List[FixtureRun]:
        """Returns upcoming fixtures for a team over the next N gameweeks."""
        runs: List[FixtureRun] = []
        target_gws = set(range(current_gw, current_gw + horizon))

        for f in self.fixtures_raw:
            gw = f.get("event")
            if gw not in target_gws or f.get("finished", False):
                continue

            if f.get("team_h") == team_id:
                opp_id = f.get("team_a")
                opp_name = self.teams_map.get(opp_id, f"Team {opp_id}")
                diff = f.get("team_h_difficulty", 3)
                runs.append(FixtureRun(
                    gameweek=gw,
                    opponent_short=opp_name,
                    is_home=True,
                    difficulty=diff
                ))
            elif f.get("team_a") == team_id:
                opp_id = f.get("team_h")
                opp_name = self.teams_map.get(opp_id, f"Team {opp_id}")
                diff = f.get("team_a_difficulty", 3)
                runs.append(FixtureRun(
                    gameweek=gw,
                    opponent_short=opp_name,
                    is_home=False,
                    difficulty=diff
                ))

        # Sort by gameweek
        runs.sort(key=lambda x: x.gameweek)
        return runs[:horizon]

    def calculate_fixture_ease(self, fixture_runs: List[FixtureRun]) -> float:
        """
        Calculates a 0.0 - 10.0 fixture ease score.
        Higher is easier / greener fixtures.
        """
        if not fixture_runs:
            return 5.0

        scores = []
        for f in fixture_runs:
            # FDR 1-5 mapped to ease scores (Home vs Away)
            if f.difficulty <= 1:
                score = 10.0 if f.is_home else 9.0
            elif f.difficulty == 2:
                score = 8.5 if f.is_home else 7.0
            elif f.difficulty == 3:
                score = 5.5 if f.is_home else 4.5
            elif f.difficulty == 4:
                score = 3.0 if f.is_home else 2.0
            else:  # 5
                score = 1.5 if f.is_home else 0.5
            scores.append(score)

        return sum(scores) / len(scores)
