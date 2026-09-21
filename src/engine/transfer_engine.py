from typing import List, Dict, Optional, Tuple, Any
from src.engine.models import Player, Position, EngineVerdict, VerdictEnum, FixtureRun
from src.engine.rules import FPLRules
from src.engine.fdr_analyzer import FDRAnalyzer

class TransferEngine:
    """Deterministic FPL transfer analysis and recommendation engine."""
    def __init__(
        self,
        players: List[Player],
        teams_map: Dict[int, str],
        fdr_analyzer: FDRAnalyzer,
        current_gw: int = 1
    ):
        self.players = players
        self.players_by_id = {p.id: p for p in players}
        self.teams_map = teams_map
        self.fdr_analyzer = fdr_analyzer
        self.current_gw = current_gw
        self._score_all_players()

    def _score_all_players(self) -> None:
        """Calculate composite rating score for every player in the league."""
        for p in self.players:
            # 1. Attach upcoming fixtures
            fixtures = self.fdr_analyzer.get_upcoming_fixtures_for_team(
                p.team_id, self.current_gw, horizon=5
            )
            p.upcoming_fixtures = fixtures
            fixture_ease = self.fdr_analyzer.calculate_fixture_ease(fixtures[:3])

            # 2. Normalized Form (0-10)
            form_val = min(max(p.form, 0.0), 10.0)

            # 3. Normalized xGI per 90 (0.0 to 1.0 mapped to 0-10)
            xgi_val = min(p.xgi_per_90 * 10.0, 10.0) if p.xgi_per_90 > 0 else min(p.form * 0.8, 10.0)

            # 4. Market Momentum (net transfers)
            net_transfers = p.transfers_in_event - p.transfers_out_event
            momentum = 5.0
            if net_transfers > 50000:
                momentum = min(5.0 + (net_transfers / 50000), 10.0)
            elif net_transfers < -50000:
                momentum = max(5.0 + (net_transfers / 50000), 0.0)

            # 5. Composite Base Score
            base_score = (0.30 * form_val) + (0.30 * xgi_val) + (0.25 * fixture_ease) + (0.15 * momentum)

            # 6. Availability factor
            play_chance = p.chance_of_playing if p.chance_of_playing is not None else 100
            if p.status in ["i", "s", "u"] or play_chance == 0:
                avail_multiplier = 0.0
            elif play_chance <= 25:
                avail_multiplier = 0.2
            elif play_chance <= 50:
                avail_multiplier = 0.5
            elif play_chance <= 75:
                avail_multiplier = 0.8
            else:
                avail_multiplier = 1.0

            p.composite_score = round(base_score * avail_multiplier, 2)

    def find_best_replacements(
        self,
        out_player: Player,
        squad: List[Player],
        bank: float,
        limit: int = 5
    ) -> List[Player]:
        """Finds top legal replacement players sorted by composite rating within budget."""
        valid_candidates: List[Player] = []

        for candidate in self.players:
            if candidate.id == out_player.id:
                continue
            
            # Check FPL rules
            is_valid, _ = FPLRules.validate_transfer(squad, out_player, candidate, bank)
            if is_valid and (candidate.chance_of_playing is None or candidate.chance_of_playing >= 75):
                valid_candidates.append(candidate)

        # Sort by composite score descending, then lower price
        valid_candidates.sort(key=lambda p: (p.composite_score, -p.price), reverse=True)
        return valid_candidates[:limit]

    def evaluate_player(
        self,
        target_player: Player,
        squad: List[Player],
        bank: float
    ) -> EngineVerdict:
        """Determines the exact deterministic verdict for a player."""
        play_chance = target_player.chance_of_playing if target_player.chance_of_playing is not None else 100
        is_flagged = target_player.status in ["i", "s", "d", "u"] or play_chance < 75
        fixtures = target_player.upcoming_fixtures[:3]
        fixture_ease = self.fdr_analyzer.calculate_fixture_ease(fixtures)
        
        # Find replacements
        replacements = self.find_best_replacements(target_player, squad, bank, limit=4)
        top_rep = replacements[0] if replacements else None

        why_facts: List[str] = []
        risk: str = ""

        # Case 1: Injured / Flagged
        if is_flagged:
            verdict = VerdictEnum.TRANSFER_OUT
            why_facts.append(f"{target_player.web_name} is flagged with {play_chance}% chance of playing ({target_player.news or 'Unavailable'})")
            if top_rep:
                why_facts.append(f"Holding £{target_player.price:.1f}m in an inactive asset loses points to rivals")
                why_facts.append(f"{top_rep.web_name} is in fine form ({top_rep.form:.1f}) with composite score {top_rep.composite_score:.1f}")
                risk = f"{top_rep.team_short_name} could suffer tactical rotation or an unexpected blank."
            else:
                why_facts.append("No viable legal replacement found within current bank balance")
                risk = "May need to take a hit (-4) or downgrade another position to free up funds."

        # Case 2: Poor Form + Tough Fixtures + Better Option Available
        elif target_player.form < 3.5 and fixture_ease < 4.0 and top_rep and top_rep.composite_score >= target_player.composite_score + 2.0:
            verdict = VerdictEnum.TRANSFER_OUT
            why_facts.append(f"{target_player.web_name} has cold form ({target_player.form:.1f}) and faces a difficult fixture run (Ease {fixture_ease:.1f}/10)")
            why_facts.append(f"{top_rep.web_name} provides superior immediate returns with form {top_rep.form:.1f} and xGI {top_rep.xgi_per_90:.2f}/90")
            risk = f"{target_player.web_name} still possesses high ceiling quality and could haul despite the tough matchup."

        # Case 3: Solid Performer or Favorable Fixtures -> KEEP
        else:
            verdict = VerdictEnum.KEEP
            why_facts.append(f"{target_player.web_name} is solid with form {target_player.form:.1f} and composite rating {target_player.composite_score:.1f}")
            why_facts.append(f"Upcoming schedule has favorable match-ups (Fixture Ease {fixture_ease:.1f}/10)")
            risk = f"A short-term blank could cost rank if rival template picks return."

        # Determine figures
        selling_price = target_player.price
        buy_price = top_rep.price if top_rep else None
        bank_after = round((bank + selling_price) - buy_price, 2) if (top_rep and verdict == VerdictEnum.TRANSFER_OUT) else bank

        # Ensure at least 2 fixtures cited
        cited_fixtures = (top_rep.upcoming_fixtures if (top_rep and verdict == VerdictEnum.TRANSFER_OUT) else target_player.upcoming_fixtures)[:2]

        return EngineVerdict(
            verdict=verdict,
            target_player=target_player,
            recommended_replacement=top_rep if verdict == VerdictEnum.TRANSFER_OUT else None,
            selling_price=selling_price,
            buy_price=buy_price,
            bank_before=bank,
            bank_after=bank_after,
            fixtures_cited=cited_fixtures,
            why_facts=why_facts,
            risk=risk,
            alternatives=replacements[1:] if len(replacements) > 1 else []
        )
