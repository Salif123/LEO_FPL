# 🦁 Leo the PL Lion — Free-Tier Agentic FPL Assistant

An autonomous, free-tier **Fantasy Premier League (FPL) Tactical Assistant** built with a **Deterministic Rule & Scoring Engine**, a **Strictly-Grounded Persona Agent (Leo)**, and an interactive **Streamlit Dashboard**.

---

## 🌟 Key Features

1. **Deterministic Rule & Analytics Engine**:
   - Live integration with the official free FPL REST API (`bootstrap-static`, `fixtures`, `picks`).
   - Mathematically enforces FPL constraints (exact budget/bank, max 3 players per club, position matching).
   - Weighted composite player scoring ($Form \times 0.30 + xGI_{90} \times 0.30 + FixtureEase \times 0.25 + Momentum \times 0.15$).
   - Home vs Away weighted Fixture Difficulty Rating (FDR 1-5).
2. **Leo the PL Lion Agent Persona**:
   - Witty, sharp, confident, Premier League savvy analyst.
   - Strictly grounded in the deterministic `<data>` packet — zero hallucinated prices, fixtures, or rules.
   - Strict 180-word output format:
     - `**VERDICT:**` 🟢 TRANSFER IN / 🔴 TRANSFER OUT / 🟡 KEEP / ⭐ CAPTAIN / 🃏 PLAY CHIP / ⏸️ SAVE CHIP
     - `**WHY:**` 2-4 sentences leading with the strongest number.
     - `**THE FIXTURES:**` Cited run with Home/Away `(H/A)` and FDR ratings.
     - `**THE MOVE:**` Exact transfer with prices and resulting bank.
     - `**RISK:**` One-line honest risk assessment.
3. **Interactive Streamlit Web Dashboard**:
   - **🏟️ Matchday Pitch View**: Full 15-player squad formation + bench with status dots.
   - **🔄 Transfer Hub**: Single-click player evaluator and top legal replacement matrix.
   - **⭐ Captaincy Showdown**: Armband projections comparing squad options vs league premiums.
   - **📈 Market Pulse & Injury Hospital**: Live price risers/fallers and official club injury reports.
   - **💬 Chat with Leo**: Real-time conversational interface with Leo.

---

## 🚀 Quick Start Guide

### 1. Environment Setup (Isolated with `uv`)
The project environment is managed using `uv`:

```bash
# Create virtual environment (if not already created)
uv venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### 2. Configuration (Optional)
Copy `.env.example` to `.env` if you want to use your free Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
MODEL_NAME=gemini-2.5-flash
```
*(Note: The app is fully functional even without an API key using our built-in high-precision deterministic synthesis).*

### 3. Run the Streamlit Web Application
```bash
streamlit run app.py
```

---

## 🧪 Running Automated Tests
```bash
pytest
```

---

## 📂 Project Architecture

```
FPl Analyzer/
├── app.py                        # Streamlit Web App Entrypoint
├── config.py                     # Central configuration & API endpoints
├── pyproject.toml / requirements.txt
├── src/
│   ├── api/
│   │   ├── fpl_client.py         # Free FPL REST API Client
│   │   └── cache_manager.py      # Dual memory & disk TTL cache
│   ├── engine/
│   │   ├── models.py             # Pydantic schemas (Player, Verdict, Squad)
│   │   ├── rules.py              # Budget & 3-per-team validator
│   │   ├── fdr_analyzer.py       # Fixture difficulty & Home/Away analyzer
│   │   ├── transfer_engine.py    # Deterministic scoring & replacement ranking
│   │   └── captain_engine.py     # Deterministic captaincy scorer
│   ├── agent/
│   │   ├── prompts.py            # Leo system prompt & grounding contract
│   │   ├── leo.py                # Gemini LLM runner + fallback synthesis
│   │   └── validator.py          # Output guardrails (word count, format, fixtures)
│   └── ui/
│       └── components.py         # Pitch styling, FDR badges, CSS
└── tests/
    ├── test_engine.py            # Engine, FDR, and validator tests
    └── test_rules.py             # FPL constraints tests
```
