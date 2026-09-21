import pytest
from src.engine.models import Player, Position, FixtureRun, VerdictEnum
from src.engine.fdr_analyzer import FDRAnalyzer
from src.engine.transfer_engine import TransferEngine
from src.engine.captain_engine import CaptainEngine
from src.agent.validator import OutputValidator
from src.agent.leo import LeoAgent

def test_fdr_analyzer():
    fixtures_raw = [
        {"event": 1, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4, "finished": False},
        {"event": 2, "team_h": 3, "team_a": 1, "team_h_difficulty": 3, "team_a_difficulty": 2, "finished": False}
    ]
    teams_map = {1: "ARS", 2: "AVL", 3: "BOU"}
    analyzer = FDRAnalyzer(fixtures_raw, teams_map)
    runs = analyzer.get_upcoming_fixtures_for_team(1, current_gw=1, horizon=2)
    assert len(runs) == 2
    assert runs[0].is_home is True
    assert runs[0].opponent_short == "AVL"
    assert runs[1].is_home is False
    assert runs[1].opponent_short == "BOU"

def test_transfer_engine_injured_flag():
    fixtures_raw = [
        {"event": 1, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4, "finished": False},
        {"event": 2, "team_h": 4, "team_a": 1, "team_h_difficulty": 3, "team_a_difficulty": 2, "finished": False}
    ]
    teams_map = {1: "ARS", 2: "AVL", 3: "BOU", 4: "BRE"}
    fdr = FDRAnalyzer(fixtures_raw, teams_map)
    
    injured_player = Player(
        id=1, web_name="Saka", first_name="Bukayo", second_name="Saka",
        team_id=1, team_short_name="ARS", position=Position.MID,
        price=10.0, form=7.0, total_points=40, status="i", chance_of_playing=25,
        news="Hamstring injury"
    )
    healthy_replacement = Player(
        id=2, web_name="Mbeumo", first_name="Bryan", second_name="Mbeumo",
        team_id=4, team_short_name="BRE", position=Position.MID,
        price=7.5, form=6.8, total_points=38, status="a", chance_of_playing=100
    )

    engine = TransferEngine([injured_player, healthy_replacement], teams_map, fdr, current_gw=1)
    verdict = engine.evaluate_player(injured_player, [injured_player], bank=0.5)

    assert verdict.verdict == VerdictEnum.TRANSFER_OUT
    assert verdict.recommended_replacement is not None
    assert verdict.recommended_replacement.id == healthy_replacement.id

def test_leo_agent_synthesis_and_validator():
    fixtures_raw = [
        {"event": 1, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4, "finished": False},
        {"event": 2, "team_h": 4, "team_a": 1, "team_h_difficulty": 3, "team_a_difficulty": 2, "finished": False},
        {"event": 3, "team_h": 4, "team_a": 3, "team_h_difficulty": 2, "team_a_difficulty": 3, "finished": False}
    ]
    teams_map = {1: "ARS", 2: "AVL", 3: "BOU", 4: "BRE"}
    fdr = FDRAnalyzer(fixtures_raw, teams_map)

    target_player = Player(
        id=1, web_name="Saka", first_name="Bukayo", second_name="Saka",
        team_id=1, team_short_name="ARS", position=Position.MID,
        price=10.0, form=7.0, total_points=40, status="i", chance_of_playing=25,
        news="Hamstring injury"
    )
    rep_player = Player(
        id=2, web_name="Mbeumo", first_name="Bryan", second_name="Mbeumo",
        team_id=4, team_short_name="BRE", position=Position.MID,
        price=7.5, form=6.8, total_points=38, status="a", chance_of_playing=100
    )

    engine = TransferEngine([target_player, rep_player], teams_map, fdr, current_gw=1)
    verdict = engine.evaluate_player(target_player, [target_player], bank=0.5)

    agent = LeoAgent()
    response = agent.generate_explanation(verdict, "Should I sell Saka?")
    
    assert "**VERDICT:** 🔴 TRANSFER OUT" in response
    assert "**THE MOVE:**" in response
    assert "**RISK:**" in response
    
    # Run validator
    is_valid, violations = OutputValidator.validate(response, verdict)
    assert is_valid, f"Validation failed: {violations}"
