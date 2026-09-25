"""
Pydantic schemas for FPL Squad Analysis, Fixture Difficulty, Predictive Scoring,
Multi-Gameweek Horizon Planning, Combinatorial Transfers, Chip Optimization,
and Mini-League Rival / Effective Ownership (EO) Analysis.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.models.player import UnderstatStats


# -------------------------------------------------------------------------
# 1. Single-Gameweek Fixtures & Scoring
# -------------------------------------------------------------------------
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
    understat_component: float = 0.0  # From npxG90 & xGChain90
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
    understat: Optional[UnderstatStats] = None
    
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


# -------------------------------------------------------------------------
# 2. Multi-Gameweek Horizon Models
# -------------------------------------------------------------------------
class GameweekProjection(BaseModel):
    """Projection for a single Gameweek within a multi-GW horizon."""
    gameweek: int
    fixtures: List[FixtureDetails] = Field(default_factory=list)
    expected_points: float = 0.0
    difficulty_avg: float = 3.0
    is_blank: bool = False
    is_double: bool = False
    tags: List[str] = Field(default_factory=list)


class PlayerHorizonAnalysis(BaseModel):
    """Player performance evaluation across an n-gameweek horizon."""
    element: int
    web_name: str
    first_name: str
    second_name: str
    team_id: int
    team_name: str
    team_short_name: str
    element_type: int
    position: str
    cost_m: float
    gw_projections: List[GameweekProjection] = Field(default_factory=list)
    total_horizon_xp: float = 0.0
    avg_fdr: float = 3.0
    fixture_run_rating: str = "Mixed"  # "Favorable 🔥", "Tough ⚠️", "Mixed ⚖️"
    understat: Optional[UnderstatStats] = None


class FixtureSwingItem(BaseModel):
    """Fixture swing evaluation for a Premier League team."""
    team_id: int
    team_name: str
    team_short_name: str
    start_gw: int
    end_gw: int
    fdr_sequence: List[int] = Field(default_factory=list)
    fdr_avg: float = 3.0
    swing_score: float = 0.0  # Positive means favorable swing, negative means hardening schedule
    sentiment: str = "Neutral"  # "Prime Target 🟢", "Toughening 🔴", "Neutral ⚪"
    key_assets: List[str] = Field(default_factory=list)


class GameweekSquadProjection(BaseModel):
    """Projected optimal squad lineup for a single future Gameweek."""
    gameweek: int
    formation: str
    starting_xi: List[PlayerAnalysis]
    bench: List[PlayerAnalysis]
    captain: CaptainChoice
    vice_captain: CaptainChoice
    projected_xp: float = 0.0


class MultiGWManagerReport(BaseModel):
    """Comprehensive Multi-Gameweek horizon report for a manager."""
    manager_id: int
    manager_name: str
    team_name: str
    start_gameweek: int
    end_gameweek: int
    horizon_length: int
    gameweek_squads: List[GameweekSquadProjection] = Field(default_factory=list)
    player_projections: List[PlayerHorizonAnalysis] = Field(default_factory=list)
    total_horizon_xp: float = 0.0
    avg_xp_per_gw: float = 0.0
    fixture_swings: List[FixtureSwingItem] = Field(default_factory=list)
    strategic_warnings: List[str] = Field(default_factory=list)


# -------------------------------------------------------------------------
# 3. Combinatorial Multi-Transfer Models
# -------------------------------------------------------------------------
class MultiTransferOption(BaseModel):
    """A multi-player transfer scenario (1, 2, or 3 players swapped simultaneously)."""
    transfer_count: int  # 1, 2, or 3
    players_out: List[PlayerAnalysis]
    players_in: List[PlayerAnalysis]
    total_cost_out_m: float
    total_cost_in_m: float
    net_cost_diff_m: float
    remaining_bank_m: float
    immediate_xp_gain: float  # Next GW xP gain
    horizon_xp_gain: float    # Horizon cumulative xP gain
    hits_taken: int           # Points deducted (-4, -8, etc.)
    net_horizon_gain: float   # horizon_xp_gain - (hits_taken * 4)
    break_even_gw: int        # Gameweek where hit is recovered
    rationale: str


class MultiTransferOptimizationReport(BaseModel):
    """Complete multi-transfer recommendation report with combinatorial rankings."""
    manager_id: int
    target_gameweek: int
    horizon_length: int
    available_free_transfers: int  # 1 to 5 FTs
    current_bank_m: float
    single_transfers: List[MultiTransferOption] = Field(default_factory=list)
    double_transfers: List[MultiTransferOption] = Field(default_factory=list)
    triple_transfers: List[MultiTransferOption] = Field(default_factory=list)
    best_overall_recommendation: Optional[MultiTransferOption] = None


# -------------------------------------------------------------------------
# 4. Chip Strategy & Valuation Models
# -------------------------------------------------------------------------
class ChipValuation(BaseModel):
    """Valuation and projected upside for activating a specific chip in a specific GW."""
    chip_name: str  # "wildcard", "freehit", "bboost", "3xc"
    recommended_gw: int
    projected_upside_xp: float  # Extra points gained vs normal baseline
    confidence_score: float     # 0.0 to 100.0
    trigger_reason: str
    alternative_gws: List[int] = Field(default_factory=list)


class ChipStrategyRoadmap(BaseModel):
    """Strategic seasonal chip roadmap for a manager."""
    manager_id: int
    chips_remaining: List[str] = Field(default_factory=list)
    chips_used: Dict[str, int] = Field(default_factory=dict)  # {chip_name: gw_used}
    recommendations: List[ChipValuation] = Field(default_factory=list)
    optimal_calendar_summary: List[str] = Field(default_factory=list)


# -------------------------------------------------------------------------
# 5. Mini-League & Effective Ownership (EO) Models
# -------------------------------------------------------------------------
class EffectiveOwnershipItem(BaseModel):
    """Effective Ownership (EO) breakdown for a specific player in a mini-league."""
    element: int
    web_name: str
    team_short_name: str
    position: str
    cost_m: float
    starting_ownership_pct: float     # % of managers starting this player
    bench_ownership_pct: float        # % of managers benching this player
    captaincy_pct: float              # % of managers captaining this player (2x)
    triple_captaincy_pct: float       # % of managers triple-captaining (3x)
    effective_ownership_pct: float    # Starting % + Captain % + (2 * TC %)
    is_owned_by_user: bool = False
    is_captained_by_user: bool = False
    user_gain_factor: float = 0.0     # (User multiplier - EO), positive = rank gain on goal
    threat_sentiment: str = "Neutral" # "High Threat 🔥", "Differential Win 💎", "Template 🛡️"


class SquadOverlapComparison(BaseModel):
    """Head-to-head squad overlap between target manager and a rival."""
    rival_entry_id: int
    rival_name: str
    rival_team_name: str
    rival_rank: int
    rival_total_points: int
    points_difference: int            # Target manager total - rival total
    shared_players_count: int         # Count of identical players (out of 15)
    overlap_percentage: float         # (shared / 15) * 100
    shared_starters_count: int        # Count of identical Starting XI players (out of 11)
    shared_player_names: List[str] = Field(default_factory=list)
    user_differentials: List[str] = Field(default_factory=list)   # Players user has that rival doesn't
    rival_differentials: List[str] = Field(default_factory=list)  # Players rival has that user doesn't
    rival_captain: str = ""
    captain_clash: bool = False       # True if both captained different players


class MiniLeagueRivalOverview(BaseModel):
    """Overview of a single rival manager in the mini-league."""
    entry_id: int
    rank: int
    last_rank: int
    manager_name: str
    team_name: str
    total_points: int
    gw_points: int
    captain_name: str
    active_chip: Optional[str] = None


class MiniLeagueAnalysisReport(BaseModel):
    """Comprehensive Mini-League analysis report with EO, overlaps, and differentials."""
    league_id: int
    league_name: str
    total_managers: int
    target_gameweek: int
    target_manager_id: Optional[int] = None
    standings: List[MiniLeagueRivalOverview] = Field(default_factory=list)
    effective_ownership: List[EffectiveOwnershipItem] = Field(default_factory=list)
    top_captains_distribution: Dict[str, float] = Field(default_factory=dict) # {CaptainName: pct}
    rival_comparisons: List[SquadOverlapComparison] = Field(default_factory=list)
    top_differential_opportunities: List[PlayerAnalysis] = Field(default_factory=list)
    tactical_summary: List[str] = Field(default_factory=list)
