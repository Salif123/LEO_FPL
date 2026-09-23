"""
Pydantic schemas for FPL Squad Analysis, Fixture Difficulty, and Predictive Player Scoring.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class FixtureDetails(BaseModel):
    """Upcoming match details for a specific player."""
    gameweek: int
    opponent_team_id: int
    opponent_name: str
    opponent_short_name: str
    is_home: bool
    difficulty: int = 3  # FDR 1 (easiest) to 5 (hardest)
    kickoff_time: Optional[str] = None
    is_blank: bool = False
    is_double: bool = False


class PlayerScoreBreakdown(BaseModel):
    """Detailed algorithmic breakdown of a player's predictive score."""
    base_form: float = 0.0
    form_component: float = 0.0
    xg_xa_component: float = 0.0
    fixture_multiplier: float = 1.0
    home_away_multiplier: float = 1.0
    availability_rate: float = 1.0
    expected_points: float = 0.0  # Projected Points (xP) for the GW
    composite_score: float = 0.0  # Scaled Index (0 - 100)
    tags: List[str] = Field(default_factory=list)


class PlayerAnalysis(BaseModel):
    """Complete analyzed player representation combining stats, fixtures, and score."""
    element: int
    web_name: str
    first_name: str
    second_name: str
    team_id: int
    team_name: str
    team_short_name: str
    element_type: int
    position: str  # GKP, DEF, MID, FWD
    cost_m: float
    total_points: int
    form: float
    expected_goals: float
    expected_assists: float
    expected_goal_involvements: float
    status: str
    chance_of_playing_next_round: Optional[int] = None
    news: Optional[str] = None
    
    # Manager's current squad setting
    squad_position: int = 1
    is_current_starter: bool = True
    is_current_bench: bool = False
    is_current_captain: bool = False
    is_current_vice_captain: bool = False

    # Upcoming Fixture & Scoring
    fixtures: List[FixtureDetails] = Field(default_factory=list)
    score_breakdown: PlayerScoreBreakdown = Field(default_factory=PlayerScoreBreakdown)

    # Optimization Recommendations
    recommended_role: str = "Starting XI"
    is_recommended_starter: bool = True
    is_recommended_captain: bool = False
    is_recommended_vice_captain: bool = False


class CaptainChoice(BaseModel):
    """Ranked captaincy recommendation with metric rationale."""
    rank: int  # 1 = Captain, 2 = Vice-Captain, 3 = Alternative / Differential
    role_name: str  # "Primary Captain (C)", "Vice-Captain (VC)", "Alternative / Differential"
    player: PlayerAnalysis
    expected_points: float
    threat_index: float
    rationale: str


class TransferRecommendation(BaseModel):
    """Algorithmic Transfer In / Transfer Out recommendation based on metric scores and budget."""
    player_out: PlayerAnalysis
    out_reason: str
    player_in: PlayerAnalysis
    in_reason: str
    expected_points_gain: float  # Difference in xP
    cost_difference_m: float  # In millions (negative means money saved)
    remaining_bank_m: float  # Bank remaining after transfer


class BenchComparisonItem(BaseModel):
    """Side-by-side comparison between current manager bench order and optimal auto-sub order."""
    player: PlayerAnalysis
    current_role: str  # e.g. "Current Sub 2 (#14)" or "Current Starter (#3)"
    recommended_role: str  # e.g. "Recommended Sub 1" or "Recommended Starter"
    is_order_changed: bool = False
    tactical_tag: str = ""  # e.g. "[⚡ 1st Outfield Cover]" or "[🛡️ Formation Safety DEF]"
    rationale: str = ""


class SquadOptimization(BaseModel):
    """Algorithmic squad optimization results (Lineup, Formation, Captaincy, Transfers, Bench, Warnings)."""
    formation: str  # e.g., "3-5-2", "3-4-3", "4-4-2"
    recommended_starting_xi: List[PlayerAnalysis]
    recommended_bench: List[PlayerAnalysis]
    captain_hierarchy: List[CaptainChoice] = Field(default_factory=list)  # Top 3 ranked choices
    recommended_captain: PlayerAnalysis
    recommended_vice_captain: PlayerAnalysis
    differential_captain: Optional[PlayerAnalysis] = None
    transfer_recommendations: List[TransferRecommendation] = Field(default_factory=list)
    bench_comparison: List[BenchComparisonItem] = Field(default_factory=list)
    bench_adjustments: List[str] = Field(default_factory=list)
    lineup_changes: List[str] = Field(default_factory=list)
    total_projected_xp: float = 0.0
    risk_warnings: List[str] = Field(default_factory=list)



class ManagerSquadAnalysisReport(BaseModel):
    """Complete report combining manager profile, analyzed players, and recommendations."""
    manager_id: int
    manager_name: str
    team_name: str
    target_gameweek: int
    next_deadline: Optional[str] = None
    players: List[PlayerAnalysis]
    optimization: SquadOptimization

