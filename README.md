# FPL Analyzer & Stats API Engine

A clean, modular Python toolkit for querying official Fantasy Premier League (FPL) data and advanced underlying statistics (xG, xA, xGChain, FDR, team loading).

---

## 📁 Project Structure

```
FPl Analyzer/
├── .env.example               # Environment variables template
├── requirements.txt           # Python dependencies
├── run_examples.py            # Complete runnable demo script
├── debug_api.py               # Interactive CLI debug & benchmarking hub
├── README.md                  # Documentation and API reference
├── debug/                     # Standalone CLI debug scripts
│   ├── 01_bootstrap.py        # Bootstrap-static & player DataFrame
│   ├── 02_player.py           # Individual player history & upcoming FDR
│   ├── 03_fixtures.py         # Premier League fixtures by Gameweek
│   ├── 04_manager.py          # Enriched manager team & squad listings
│   ├── 05_live.py             # Live matchday points & BPS
│   ├── 06_understat.py        # Understat xG, xGChain & xGBuildup
│   └── 07_squad_analysis.py   # Squad scoring & lineup optimization
└── src/
    ├── __init__.py
    ├── config.py              # Endpoints and configuration constants
    ├── api/                   # API clients and HTTP layer
    │   ├── base_client.py     # Base HTTP client with retry logic & error handling
    │   ├── fpl_client.py      # Complete Official FPL API client
    │   └── understat_client.py# Understat xG & shot map scraper
    ├── analysis/              # Squad analysis & scoring engine
    │   └── squad_analyzer.py  # Fixture evaluation, predictive xP & lineup optimizer
    └── models/                # Pydantic schemas
        ├── player.py          # Player & match performance schemas
        ├── manager.py         # Manager profile, squad picks & enriched team schemas
        └── analysis.py        # Fixture details, scoring breakdown & optimization schemas
```

---

## 🚀 How to Set Up and Run

### 1. Install Dependencies
Make sure you are in your virtual environment and run:
```powershell
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env` and fill in your default Manager ID if desired:
```powershell
cp .env.example .env
```

### 3. Run the API Demo
To execute and inspect all the live API calls:
```powershell
python run_examples.py
```

### 4. Run the Dedicated Squad Analyzer
```powershell
python debug/07_squad_analysis.py [manager_id] [gameweek]
```

---

## 🔌 API Usage Guide & Code Examples

### 1. Official FPL Bootstrap (All Players, Teams, xG, xA)
```python
from src.api.fpl_client import FPLClient

client = FPLClient()

# Get all 600+ players in a structured Pandas DataFrame with parsed xG
df = client.get_players_df()
print(df[["web_name", "team_name", "position", "cost_m", "expected_goals", "expected_assists"]].head())
```

### 2. Individual Player History & Upcoming Fixtures
```python
# Detailed match breakdown (GW by GW) and upcoming FDR
player_summary = client.get_element_summary(player_id=355) # e.g. Erling Haaland
print(player_summary["history"][-1])   # Last match stats (xG, xA, BPS, points)
print(player_summary["fixtures"][:3])  # Next 3 upcoming fixtures
```

### 3. FPL Manager Squad Loading & Team Listings
```python
manager_id = 1209336  # Replace with any FPL Manager ID
current_gw = 5

# 1. Enriched Manager Team Listing (Full squad, Starting XI, Bench, Costs, xG, xA)
team = client.get_manager_team(manager_id=manager_id, event_id=current_gw)
print(f"Team: {team['team_name']} | Manager: {team['manager_name']}")
print(f"Squad Value: £{team['team_value_m']}m | Bank: £{team['bank_m']}m")

for starter in team['starting_xi']:
    cap = " (C)" if starter['is_captain'] else (" (VC)" if starter['is_vice_captain'] else "")
    print(f"  {starter['web_name']}{cap} ({starter['team_short_name']} - {starter['position']}) - £{starter['cost_m']}m | Pts: {starter['total_points']}")

# 2. Get Manager Squad as a formatted Pandas DataFrame
team_df = client.get_manager_team_df(manager_id=manager_id, event_id=current_gw)
print(team_df[["pos_no", "role", "player", "team", "pos", "cost_m", "captaincy", "total_pts", "xG", "xA"]])
```

### 4. Squad Predictive Scoring, Captaincy, Auto-Sub Strategy & Transfer Recommendations
```python
# Evaluates upcoming fixtures, Home/Away advantage, FDR (1-5), form, xG/xA, and injuries
report = client.analyze_manager_squad(manager_id=1209336)
opt = report.optimization

# 1. Optimal Lineup & Projected Points
print(f"Target GW: {report.target_gameweek} | Recommended Formation: {opt.formation} (Projected Total: {opt.total_projected_xp} xP)")

# 2. Top 3 Captaincy Hierarchy
print("\nTop 3 Captaincy Hierarchy:")
for c in opt.captain_hierarchy:
    print(f"  #{c.rank} {c.role_name}: {c.player.web_name} ({c.expected_points} xP) - {c.rationale}")

# 3. Bench Optimization & Tactical Auto-Sub Order
print("\nBench Optimization & Auto-Subs:")
for lc in opt.lineup_changes:
    print(f"  • {lc}")
for b_item in opt.bench_comparison:
    print(f"  • {b_item.player.web_name}: {b_item.tactical_tag}")

# 4. Metric-Driven Transfer Recommendations
print("\nTransfer Recommendations:")
for tr in opt.transfer_recommendations:
    print(f"  🔴 OUT: {tr.player_out.web_name} ({tr.out_reason})")
    print(f"  🟢 IN : {tr.player_in.web_name} ({tr.in_reason})")
    print(f"  📈 Net Gain: +{tr.expected_points_gain} xP | Bank Left: £{tr.remaining_bank_m}m\n")

# 5. Export scored squad as a sorted DataFrame
analysis_df = client.get_squad_analysis_df(manager_id=1209336)
print(analysis_df[["Player", "Team", "Pos", "Opponent (FDR)", "Form", "xP", "Score (0-100)", "Recommended Role"]].head(11))
```

### 5. Pre-Deadline Transfers & FPL Privacy Rules

#### Why aren't transfers for an upcoming Gameweek visible on the public API immediately?
In official Fantasy Premier League (FPL):
- The public API (`/api/entry/{manager_id}/event/{gw}/picks/`) **strictly locks and hides** all transfers, team picks, and captaincy choices for upcoming Gameweeks until that Gameweek's deadline officially expires.
- This prevents rival managers in mini-leagues from scouting and copying your pre-deadline transfers.
- Before the deadline, the public API only exposes the manager's latest published squad (e.g. GW 5).

#### 3 Ways to Analyze Pre-Deadline Squads:

1. **Automatic Forward-Projection (Default)**:
   The engine automatically loads your latest confirmed squad and analyzes it against upcoming GW fixtures (e.g. GW 6):
   ```python
   report = client.analyze_manager_squad(manager_id=1209336, gw=6)
   ```

2. **Simulate / Override Transfers on the fly**:
   Test prospective transfers before or after making them on the FPL site:
   ```python
   # Replace Player ID 355 with Player ID 19
   report = client.analyze_manager_squad(
       manager_id=1209336,
       gw=6,
       transfers_out=[355],  # Haaland
       transfers_in=[19]     # Saka
   )
   ```

3. **Authenticated Live Sync (Requires Session Cookie)**:
   Set `FPL_COOKIE` in your `.env` or pass `fpl_cookie` to directly query your private `/api/my-team/{manager_id}/` endpoint:
   ```python
   # Fetches your live saved pre-deadline transfers & live bank balance
   report = client.analyze_manager_squad(
       manager_id=1209336,
       fpl_cookie="your_pl_profile_cookie_here"
   )
   ```

---

### 6. Advanced xG, xGChain & Shot Maps (Understat)
```python
from src.api.understat_client import UnderstatClient

understat = UnderstatClient()
epl_players = understat.get_league_players() # All EPL players with xGChain & xGBuildup
print(epl_players[0])
```
