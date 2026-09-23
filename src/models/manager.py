"""
Pydantic schemas for FPL Managers, Squad Picks, and History.
"""
from typing import List, Optional
from pydantic import BaseModel


class SquadPick(BaseModel):
    """A single player pick in a manager's gameweek squad."""
    element: int  # Player ID
    position: int  # 1-15 (1-11 Starting, 12-15 Bench)
    multiplier: int  # 1 = Regular, 2 = Captain, 3 = Triple Captain, 0 = Benched
    is_captain: bool
    is_vice_captain: bool


class EntryHistory(BaseModel):
    """Gameweek summary for a manager squad."""
    event: int
    points: int
    total_points: int
    rank: Optional[int] = None
    overall_rank: Optional[int] = None
    bank: int
    value: int
    event_transfers: int
    event_transfers_cost: int
    points_on_bench: int


class ManagerSquad(BaseModel):
    """Complete squad selection for a Gameweek."""
    active_chip: Optional[str] = None
    picks: List[SquadPick]
    entry_history: EntryHistory


class ManagerProfile(BaseModel):
    """High-level manager profile."""
    id: int
    player_first_name: str
    player_last_name: str
    name: str  # Team Name
    summary_overall_points: int
    summary_overall_rank: Optional[int] = None
    summary_event_points: Optional[int] = None
    summary_event_rank: Optional[int] = None
    current_event: Optional[int] = None


class ManagerTeamPlayer(BaseModel):
    """Enriched player representation in a manager's squad."""
    element: int  # Player ID
    web_name: str
    first_name: str
    second_name: str
    team_id: int
    team_name: str
    team_short_name: str
    element_type: int
    position: str  # GKP, DEF, MID, FWD
    squad_position: int  # 1-15
    is_starter: bool  # True if 1-11
    is_bench: bool  # True if 12-15
    multiplier: int  # 0 (bench), 1 (starter), 2 (captain), 3 (triple captain)
    is_captain: bool
    is_vice_captain: bool
    cost_m: float  # Price in millions
    total_points: int
    form: float = 0.0
    expected_goals: float = 0.0
    expected_assists: float = 0.0
    expected_goal_involvements: float = 0.0
    status: str = "a"
    news: Optional[str] = None
    chance_of_playing_next_round: Optional[int] = None


class ManagerTeamListing(BaseModel):
    """Comprehensive team listing for a manager in a specific Gameweek."""
    manager_id: int
    manager_name: str
    team_name: str
    event_id: int
    active_chip: Optional[str] = None
    entry_history: Optional[EntryHistory] = None
    starting_xi: List[ManagerTeamPlayer]
    bench: List[ManagerTeamPlayer]
    players: List[ManagerTeamPlayer]  # All 15 players
    team_value_m: float = 0.0
    bank_m: float = 0.0

