from typing import List, Tuple
from src.engine.models import Player

MAX_PLAYERS_PER_CLUB = 3

class FPLRules:
    """Deterministic validation of official FPL rules and constraints."""

    @staticmethod
    def validate_transfer(
        current_squad: List[Player],
        out_player: Player,
        in_player: Player,
        bank: float
    ) -> Tuple[bool, str]:
        """
        Validates if replacing out_player with in_player is legal under FPL rules.
        Returns (is_valid, error_reason).
        """
        # 1. Position match check
        if out_player.position != in_player.position:
            return False, f"Position mismatch: Cannot replace {out_player.position.label} with {in_player.position.label}."

        # 2. Cannot buy a player already in the squad
        squad_ids = {p.id for p in current_squad}
        if in_player.id in squad_ids:
            return False, f"{in_player.web_name} is already in your squad."

        # 3. Budget check (Bank + selling price)
        total_funds = round(out_player.price + bank, 2)
        if round(in_player.price, 2) > total_funds:
            shortfall = round(in_player.price - total_funds, 2)
            return False, f"Insufficient funds: Need £{in_player.price:.1f}m, available is £{total_funds:.1f}m (short by £{shortfall:.1f}m)."

        # 4. Max 3 players per club check
        club_counts: dict[int, int] = {}
        for p in current_squad:
            club_counts[p.team_id] = club_counts.get(p.team_id, 0) + 1

        # Decrement the out player's club
        club_counts[out_player.team_id] = club_counts.get(out_player.team_id, 1) - 1

        # Check target club count
        target_club_count = club_counts.get(in_player.team_id, 0)
        if target_club_count >= MAX_PLAYERS_PER_CLUB:
            return False, f"Club limit exceeded: Already have {target_club_count} players from {in_player.team_short_name} (Max {MAX_PLAYERS_PER_CLUB})."

        return True, "Valid transfer"

    @staticmethod
    def count_by_club(squad: List[Player]) -> dict[str, int]:
        """Returns a tally of squad players by club short name."""
        tally: dict[str, int] = {}
        for p in squad:
            tally[p.team_short_name] = tally.get(p.team_short_name, 0) + 1
        return tally
