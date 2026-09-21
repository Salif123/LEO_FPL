from typing import List, Tuple
from src.engine.models import Player, EngineVerdict, VerdictEnum, FixtureRun

class CaptainEngine:
    """Deterministic captaincy selection engine."""
    def __init__(self, current_gw: int = 1):
        self.current_gw = current_gw

    def calculate_captain_score(self, player: Player) -> float:
        """Calculates single-gameweek captaincy projection score."""
        # Check health
        play_chance = player.chance_of_playing if player.chance_of_playing is not None else 100
        if player.status in ["i", "s", "u"] or play_chance < 75:
            return 0.0

        # Form (0-10)
        form_score = min(max(player.form, 0.0), 10.0)

        # xGI/90 (0-10)
        xgi_score = min(player.xgi_per_90 * 10.0, 10.0) if player.xgi_per_90 > 0 else min(player.form * 0.8, 10.0)

        # Immediate fixture difficulty
        next_fix = player.upcoming_fixtures[0] if player.upcoming_fixtures else None
        if next_fix:
            if next_fix.difficulty <= 2:
                fix_score = 9.5 if next_fix.is_home else 8.0
            elif next_fix.difficulty == 3:
                fix_score = 6.0 if next_fix.is_home else 4.5
            else:
                fix_score = 3.0 if next_fix.is_home else 1.5
        else:
            fix_score = 5.0

        score = (0.40 * form_score) + (0.35 * xgi_score) + (0.25 * fix_score)
        return round(score, 2)

    def select_best_captains(self, squad: List[Player]) -> Tuple[Player, Player, List[Tuple[Player, float]]]:
        """Returns (best_captain, vice_captain, all_ranked_scores)."""
        scored = [(p, self.calculate_captain_score(p)) for p in squad]
        scored.sort(key=lambda x: x[1], reverse=True)

        captain = scored[0][0] if scored else squad[0]
        vice_captain = scored[1][0] if len(scored) > 1 else squad[0]
        return captain, vice_captain, scored

    def evaluate_captaincy(self, squad: List[Player], target_player: Player) -> EngineVerdict:
        """Evaluates captaincy for a target player against the squad options."""
        best_c, best_vc, ranked = self.select_best_captains(squad)

        why_facts = [
            f"{best_c.web_name} has the highest projected ceiling with form {best_c.form:.1f} and xGI {best_c.xgi_per_90:.2f}/90",
            f"Next matchup is {best_c.upcoming_fixtures[0].formatted if best_c.upcoming_fixtures else 'favorable'}",
            f"Vice-captain safety option: {best_vc.web_name}"
        ]

        cited_fixtures = best_c.upcoming_fixtures[:2]
        risk = "Any premium captain carries the risk of a low-scoring match or penalty miss."

        return EngineVerdict(
            verdict=VerdictEnum.CAPTAIN,
            target_player=best_c,
            recommended_replacement=best_vc,
            selling_price=best_c.price,
            bank_before=0.0,
            fixtures_cited=cited_fixtures,
            why_facts=why_facts,
            risk=risk,
            alternatives=[p for p, s in ranked[1:4]]
        )
