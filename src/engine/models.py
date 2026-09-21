from enum import IntEnum, Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Position(IntEnum):
    GKP = 1
    DEF = 2
    MID = 3
    FWD = 4

    @property
    def label(self) -> str:
        return {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}[self.value]

class VerdictEnum(str, Enum):
    TRANSFER_IN = "🟢 TRANSFER IN"
    TRANSFER_OUT = "🔴 TRANSFER OUT"
    KEEP = "🟡 KEEP"
    CAPTAIN = "⭐ CAPTAIN"
    PLAY_CHIP = "🃏 PLAY CHIP"
    SAVE_CHIP = "⏸️ SAVE CHIP"

class FixtureRun(BaseModel):
    gameweek: int
    opponent_short: str
    is_home: bool
    difficulty: int  # 1 (easiest) to 5 (hardest)

    @property
    def formatted(self) -> str:
        loc = "H" if self.is_home else "A"
        return f"{self.opponent_short} ({loc}, FDR {self.difficulty})"

class Player(BaseModel):
    id: int
    web_name: str
    first_name: str
    second_name: str
    team_id: int
    team_short_name: str
    position: Position
    price: float  # e.g. 7.5 (£m)
    form: float  # e.g. 6.8
    total_points: int
    xg: float = 0.0
    xa: float = 0.0
    xgi_per_90: float = 0.0
    ict_index: float = 0.0
    status: str = "a"  # 'a', 'd', 'i', 's', 'u'
    chance_of_playing: Optional[int] = 100
    news: str = ""
    transfers_in_event: int = 0
    transfers_out_event: int = 0
    cost_change_event: int = 0
    selected_by_percent: float = 0.0
    upcoming_fixtures: List[FixtureRun] = []
    composite_score: float = 0.0

    @property
    def display_name(self) -> str:
        return f"{self.web_name} ({self.team_short_name}, £{self.price:.1f}m)"

class SquadPick(BaseModel):
    element_id: int
    position: int  # 1 to 15 (1-11 starters, 12-15 bench)
    is_captain: bool = False
    is_vice_captain: bool = False
    multiplier: int = 1
    player: Optional[Player] = None

class ManagerSquad(BaseModel):
    team_id: int
    manager_name: str
    team_name: str
    overall_points: int = 0
    overall_rank: Optional[int] = None
    bank: float = 0.0  # £m
    free_transfers: int = 1
    picks: List[SquadPick] = []

class TransferCandidate(BaseModel):
    player: Player
    score_delta: float
    price_diff: float
    reasons: List[str] = []

class EngineVerdict(BaseModel):
    verdict: VerdictEnum
    target_player: Player
    recommended_replacement: Optional[Player] = None
    selling_price: float
    buy_price: Optional[float] = None
    bank_before: float
    bank_after: Optional[float] = None
    fixtures_cited: List[FixtureRun] = []
    why_facts: List[str] = []
    risk: str = ""
    alternatives: List[Player] = []
    meta: Dict[str, Any] = {}

    def to_xml_data_packet(self) -> str:
        """Converts the deterministic engine verdict into the strict <data> XML payload for Leo."""
        fix_lines = "\n".join([f"    - GW{f.gameweek}: {f.formatted}" for f in self.fixtures_cited])
        
        rep_section = ""
        if self.recommended_replacement:
            rep_section = f"""  <recommended_replacement>{self.recommended_replacement.display_name}</recommended_replacement>
  <buy_price>£{self.buy_price:.1f}m</buy_price>
  <bank_after>£{self.bank_after:.1f}m</bank_after>"""
        
        facts_str = "; ".join(self.why_facts)
        alts_str = ", ".join([a.display_name for a in self.alternatives]) or "none"

        xml = f"""<data>
  <target_player>{self.target_player.display_name}</target_player>
  <status>{self.target_player.status} (Playing Chance: {self.target_player.chance_of_playing or 100}%)</status>
  <news>{self.target_player.news or "Fully fit"}</news>
  <selling_price>£{self.selling_price:.1f}m</selling_price>
  <bank_before>£{self.bank_before:.1f}m</bank_before>
  <verdict>{self.verdict.value}</verdict>
{rep_section}
  <fixtures_cited>
{fix_lines}
  </fixtures_cited>
  <key_facts>{facts_str}</key_facts>
  <risk>{self.risk}</risk>
  <alternatives>{alts_str}</alternatives>
</data>"""
        return xml
