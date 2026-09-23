"""
Pydantic schemas for FPL Players and Performance Statistics.
"""
from typing import Optional
from pydantic import BaseModel, Field


class Player(BaseModel):
    """FPL Player Model representation."""
    id: int
    web_name: str
    first_name: str
    second_name: str
    team: int
    team_name: Optional[str] = None
    element_type: int
    position: Optional[str] = None
    now_cost: int
    cost_m: Optional[float] = None
    total_points: int
    points_per_game: str
    form: str
    selected_by_percent: str
    minutes: int
    goals_scored: int
    assists: int
    clean_sheets: int
    expected_goals: float = 0.0
    expected_assists: float = 0.0
    expected_goal_involvements: float = 0.0
    expected_goals_conceded: float = 0.0
    ict_index: str
    status: str
    news: Optional[str] = None
    chance_of_playing_next_round: Optional[int] = None


class PlayerSummary(BaseModel):
    """Player performance summary for match history."""
    element: int
    fixture: int
    opponent_team: int
    total_points: int
    was_home: bool
    minutes: int
    goals_scored: int
    assists: int
    clean_sheets: int
    expected_goals: float = 0.0
    expected_assists: float = 0.0
    expected_goal_involvements: float = 0.0
    expected_goals_conceded: float = 0.0
    bonus: int
    bps: int
