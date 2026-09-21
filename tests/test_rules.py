import pytest
from src.engine.models import Player, Position
from src.engine.rules import FPLRules

@pytest.fixture
def sample_squad():
    squad = []
    # 2 GKPs
    squad.append(Player(id=1, web_name="Raya", first_name="David", second_name="Raya", team_id=1, team_short_name="ARS", position=Position.GKP, price=5.5, form=5.0, total_points=25))
    squad.append(Player(id=2, web_name="Turner", first_name="Matt", second_name="Turner", team_id=7, team_short_name="CRY", position=Position.GKP, price=4.0, form=1.0, total_points=5))
    
    # 5 DEFs (including 2 Arsenal)
    squad.append(Player(id=3, web_name="Gabriel", first_name="Gabriel", second_name="Magalhaes", team_id=1, team_short_name="ARS", position=Position.DEF, price=6.0, form=6.0, total_points=30))
    squad.append(Player(id=4, web_name="Saliba", first_name="William", second_name="Saliba", team_id=1, team_short_name="ARS", position=Position.DEF, price=6.0, form=5.5, total_points=28))
    squad.append(Player(id=5, web_name="Alexander-Arnold", first_name="Trent", second_name="Alexander-Arnold", team_id=12, team_short_name="LIV", position=Position.DEF, price=7.0, form=6.5, total_points=32))
    squad.append(Player(id=6, web_name="Robinson", first_name="Antonee", second_name="Robinson", team_id=9, team_short_name="FUL", position=Position.DEF, price=4.6, form=4.0, total_points=18))
    squad.append(Player(id=7, web_name="Konsa", first_name="Ezri", second_name="Konsa", team_id=2, team_short_name="AVL", position=Position.DEF, price=4.5, form=3.5, total_points=15))

    # 5 MIDs
    squad.append(Player(id=8, web_name="Palmer", first_name="Cole", second_name="Palmer", team_id=6, team_short_name="CHE", position=Position.MID, price=10.8, form=8.0, total_points=45))
    squad.append(Player(id=9, web_name="Mbeumo", first_name="Bryan", second_name="Mbeumo", team_id=4, team_short_name="BRE", position=Position.MID, price=7.5, form=6.5, total_points=35))
    squad.append(Player(id=10, web_name="Semenyo", first_name="Antoine", second_name="Semenyo", team_id=3, team_short_name="BOU", position=Position.MID, price=5.6, form=5.0, total_points=24))
    squad.append(Player(id=11, web_name="Rogers", first_name="Morgan", second_name="Rogers", team_id=2, team_short_name="AVL", position=Position.MID, price=5.2, form=4.5, total_points=20))
    squad.append(Player(id=12, web_name="Winks", first_name="Harry", second_name="Winks", team_id=11, team_short_name="LEI", position=Position.MID, price=4.5, form=2.0, total_points=10))

    # 3 FWDs
    squad.append(Player(id=13, web_name="Haaland", first_name="Erling", second_name="Haaland", team_id=13, team_short_name="MCI", position=Position.FWD, price=15.2, form=9.5, total_points=55))
    squad.append(Player(id=14, web_name="Watkins", first_name="Ollie", second_name="Watkins", team_id=2, team_short_name="AVL", position=Position.FWD, price=9.0, form=5.0, total_points=28))
    squad.append(Player(id=15, web_name="Wood", first_name="Chris", second_name="Wood", team_id=15, team_short_name="NFO", position=Position.FWD, price=6.1, form=5.5, total_points=27))

    return squad

def test_position_mismatch(sample_squad):
    out_p = sample_squad[7]  # Palmer (MID)
    in_p = sample_squad[13] # Haaland (FWD)
    is_valid, msg = FPLRules.validate_transfer(sample_squad, out_p, in_p, bank=10.0)
    assert not is_valid
    assert "Position mismatch" in msg

def test_budget_exceeded(sample_squad):
    out_p = sample_squad[11] # Winks (£4.5m)
    expensive_mid = Player(id=99, web_name="Salah", first_name="Mohamed", second_name="Salah", team_id=12, team_short_name="LIV", position=Position.MID, price=12.5, form=8.0, total_points=50)
    is_valid, msg = FPLRules.validate_transfer(sample_squad, out_p, expensive_mid, bank=1.0)
    assert not is_valid
    assert "Insufficient funds" in msg

def test_club_limit_exceeded(sample_squad):
    # Squad already has Raya (ARS), Gabriel (ARS), Saliba (ARS) -> 3 Arsenal players
    out_p = sample_squad[7] # Palmer (CHE)
    arsenal_mid = Player(id=98, web_name="Saka", first_name="Bukayo", second_name="Saka", team_id=1, team_short_name="ARS", position=Position.MID, price=10.0, form=7.0, total_points=40)
    is_valid, msg = FPLRules.validate_transfer(sample_squad, out_p, arsenal_mid, bank=2.0)
    assert not is_valid
    assert "Club limit exceeded" in msg

def test_valid_transfer(sample_squad):
    out_p = sample_squad[11] # Winks (£4.5m)
    budget_mid = Player(id=97, web_name="Smith Rowe", first_name="Emile", second_name="Smith Rowe", team_id=9, team_short_name="FUL", position=Position.MID, price=5.6, form=5.5, total_points=26)
    is_valid, msg = FPLRules.validate_transfer(sample_squad, out_p, budget_mid, bank=1.5)
    assert is_valid
    assert "Valid transfer" in msg
