import streamlit as st
import pandas as pd
from typing import List, Dict, Optional

from config import GEMINI_API_KEY, MODEL_NAME
from src.api.fpl_client import FPLClient
from src.engine.models import Player, Position, FixtureRun, ManagerSquad, SquadPick, VerdictEnum
from src.engine.fdr_analyzer import FDRAnalyzer
from src.engine.transfer_engine import TransferEngine
from src.engine.captain_engine import CaptainEngine
from src.engine.rules import FPLRules
from src.agent.leo import LeoAgent
from src.ui.components import CUSTOM_CSS, render_fdr_badge, render_fixtures_html

# Page Configuration
st.set_page_config(
    page_title="Leo the PL Lion | FPL Assistant",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply styling
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ----------------- DATA LOADING & CACHING -----------------
@st.cache_data(ttl=300, show_spinner=False)
def load_fpl_data():
    """Fetches bootstrap data and fixtures from the official free FPL API."""
    client = FPLClient()
    bootstrap = client.get_bootstrap_static()
    fixtures_raw = client.get_fixtures()
    current_gw = client.get_current_gameweek()

    # Build teams map
    teams_map = {t["id"]: t["short_name"] for t in bootstrap.get("teams", [])}

    # Initialize FDR analyzer
    fdr_analyzer = FDRAnalyzer(fixtures_raw, teams_map)

    # Parse players
    players: List[Player] = []
    for el in bootstrap.get("elements", []):
        team_id = el.get("team")
        team_short = teams_map.get(team_id, "UNK")
        p = Player(
            id=el["id"],
            web_name=el.get("web_name", "Unknown"),
            first_name=el.get("first_name", ""),
            second_name=el.get("second_name", ""),
            team_id=team_id,
            team_short_name=team_short,
            position=Position(el.get("element_type", 1)),
            price=el.get("now_cost", 50) / 10.0,
            form=float(el.get("form") or 0.0),
            total_points=el.get("total_points", 0),
            xg=float(el.get("expected_goals") or 0.0),
            xa=float(el.get("expected_assists") or 0.0),
            xgi_per_90=float(el.get("expected_goal_involvements_per_90") or 0.0),
            ict_index=float(el.get("ict_index") or 0.0),
            status=el.get("status", "a"),
            chance_of_playing=el.get("chance_of_playing_next_round"),
            news=el.get("news", ""),
            transfers_in_event=el.get("transfers_in_event", 0),
            transfers_out_event=el.get("transfers_out_event", 0),
            cost_change_event=el.get("cost_change_event", 0),
            selected_by_percent=float(el.get("selected_by_percent") or 0.0)
        )
        players.append(p)

    transfer_engine = TransferEngine(players, teams_map, fdr_analyzer, current_gw)
    captain_engine = CaptainEngine(current_gw)

    return {
        "bootstrap": bootstrap,
        "teams_map": teams_map,
        "players": players,
        "players_by_id": {p.id: p for p in players},
        "fdr_analyzer": fdr_analyzer,
        "transfer_engine": transfer_engine,
        "captain_engine": captain_engine,
        "current_gw": current_gw,
    }

def get_demo_squad(players_by_id: Dict[int, Player]) -> ManagerSquad:
    """Provides a realistic sample squad if no FPL Team ID is entered."""
    # Pick top popular players across positions
    sorted_players = sorted(players_by_id.values(), key=lambda p: p.selected_by_percent, reverse=True)
    gkps = [p for p in sorted_players if p.position == Position.GKP][:2]
    defs = [p for p in sorted_players if p.position == Position.DEF][:5]
    mids = [p for p in sorted_players if p.position == Position.MID][:5]
    fwds = [p for p in sorted_players if p.position == Position.FWD][:3]

    squad_players = gkps + defs + mids + fwds
    picks = []
    for idx, p in enumerate(squad_players, 1):
        picks.append(SquadPick(
            element_id=p.id,
            position=idx,
            is_captain=(idx == 8),  # Midfielder captain
            is_vice_captain=(idx == 13), # Forward vice-captain
            player=p
        ))

    return ManagerSquad(
        team_id=101,
        manager_name="Sample FPL Master",
        team_name="The Lion's Pride FC",
        overall_points=320,
        overall_rank=45210,
        bank=0.5,
        free_transfers=1,
        picks=picks
    )

def fetch_user_squad(team_id: int, current_gw: int, players_by_id: Dict[int, Player]) -> Optional[ManagerSquad]:
    """Fetches manager squad from the official FPL API by team ID."""
    client = FPLClient()
    try:
        entry = client.get_manager_entry(team_id)
        # Try current gameweek picks, or previous gameweek if current isn't finalized
        try:
            picks_data = client.get_manager_picks(team_id, current_gw)
        except Exception:
            picks_data = client.get_manager_picks(team_id, max(1, current_gw - 1))

        picks = []
        for pick in picks_data.get("picks", []):
            el_id = pick["element"]
            p = players_by_id.get(el_id)
            picks.append(SquadPick(
                element_id=el_id,
                position=pick["position"],
                is_captain=pick.get("is_captain", False),
                is_vice_captain=pick.get("is_vice_captain", False),
                multiplier=pick.get("multiplier", 1),
                player=p
            ))

        bank = picks_data.get("entry_history", {}).get("bank", 0) / 10.0
        free_transfers = picks_data.get("entry_history", {}).get("event_transfers", 1)

        return ManagerSquad(
            team_id=team_id,
            manager_name=f"{entry.get('player_first_name', '')} {entry.get('player_last_name', '')}",
            team_name=entry.get("name", f"Team {team_id}"),
            overall_points=entry.get("summary_overall_points", 0),
            overall_rank=entry.get("summary_overall_rank"),
            bank=bank,
            free_transfers=1,
            picks=picks
        )
    except Exception as e:
        st.sidebar.error(f"Could not load FPL Team ID {team_id}: {e}")
        return None

# ----------------- MAIN APP INITIALIZATION -----------------
data = load_fpl_data()
players_by_id = data["players_by_id"]
all_players = data["players"]
transfer_engine: TransferEngine = data["transfer_engine"]
captain_engine: CaptainEngine = data["captain_engine"]
current_gw = data["current_gw"]

# ----------------- SIDEBAR CONTROLS -----------------
with st.sidebar:
    st.image("https://fantasy.premierleague.com/static/libsass/pl/dist/img/pl-lion.svg", width=90)
    st.title("🦁 Leo the PL Lion")
    st.caption("Agentic FPL Tactical Assistant")
    
    st.divider()
    st.subheader("⚙️ Manager Setup")
    user_team_id_input = st.text_input("Enter FPL Team ID (optional)", placeholder="e.g. 123456")
    use_demo = st.checkbox("Use Demo Top-10k Squad", value=not bool(user_team_id_input))

    st.subheader("🔑 Gemini Intelligence")
    api_key_input = st.text_input("Gemini API Key (optional)", type="password", value=GEMINI_API_KEY or "")
    if not api_key_input or api_key_input == "your_gemini_api_key_here":
        st.info("💡 Running in High-Precision Grounded Mode. Enter an API key for dynamic Gemini voice.")

    st.divider()
    if st.button("🔄 Refresh Live FPL Data"):
        st.cache_data.clear()
        st.rerun()

# Determine active squad
active_squad: ManagerSquad
if user_team_id_input and not use_demo:
    try:
        tid = int(user_team_id_input.strip())
        squad_res = fetch_user_squad(tid, current_gw, players_by_id)
        active_squad = squad_res or get_demo_squad(players_by_id)
    except ValueError:
        st.sidebar.warning("Please enter a valid numeric FPL Team ID.")
        active_squad = get_demo_squad(players_by_id)
else:
    active_squad = get_demo_squad(players_by_id)

leo_agent = LeoAgent(api_key=api_key_input if api_key_input != "your_gemini_api_key_here" else None)

# ----------------- HEADER BANNER -----------------
st.markdown(f"""
<div class="leo-header">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <div>
            <h1 style="margin: 0; font-weight: 800; font-size: 2.2rem; color: #00ff87;">🦁 LEO THE PL LION</h1>
            <p style="margin: 4px 0 0 0; font-size: 1.1rem; opacity: 0.9;">
                Gameweek <strong>{current_gw}</strong> Analysis • Squad: <strong>{active_squad.team_name}</strong> ({active_squad.manager_name})
            </p>
        </div>
        <div style="text-align: right; margin-top: 8px;">
            <span style="background: rgba(0,255,135,0.15); border: 1px solid #00ff87; padding: 6px 12px; border-radius: 8px; font-weight: 600;">
                💰 Bank: £{active_squad.bank:.1f}m
            </span>
            <span style="background: rgba(255,40,130,0.15); border: 1px solid #ff2882; padding: 6px 12px; border-radius: 8px; font-weight: 600; margin-left: 6px;">
                🏆 Rank: #{active_squad.overall_rank:,}
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- TABS NAVIGATION -----------------
tab_pitch, tab_captain, tab_market, tab_chat = st.tabs([
    "📋 Pitch & Transfer Hub",
    "⭐ Captaincy Showdown",
    "📈 Live Market & Injury Hospital",
    "💬 Chat with Leo"
])

# ----------------- TAB 1: PITCH & TRANSFER HUB -----------------
with tab_pitch:
    col_pitch, col_analysis = st.columns([1.2, 1.0])

    squad_players = [p.player for p in active_squad.picks if p.player]

    with col_pitch:
        st.subheader("🏟️ Active Matchday Squad")
        
        # Group by position
        starters = active_squad.picks[:11]
        bench = active_squad.picks[11:]

        st.markdown('<div class="pitch-container">', unsafe_allow_html=True)
        
        # GKPs
        gks = [p for p in starters if p.player and p.player.position == Position.GKP]
        g_cols = st.columns(len(gks) or 1)
        for i, pick in enumerate(gks):
            with g_cols[i]:
                p = pick.player
                status_icon = "🟢" if (p.chance_of_playing is None or p.chance_of_playing == 100) else "🔴"
                capt = " 👑 (C)" if pick.is_captain else (" (VC)" if pick.is_vice_captain else "")
                st.markdown(f"""
                <div class="player-card">
                    <div style="font-weight: 800; font-size: 1.05rem;">{p.web_name}{capt}</div>
                    <div style="font-size: 0.85rem; color: #00ff87;">{p.team_short_name} • £{p.price:.1f}m {status_icon}</div>
                    <div style="font-size: 0.8rem; opacity: 0.8;">Form: {p.form:.1f} • Score: {p.composite_score:.1f}</div>
                </div>
                """, unsafe_allow_html=True)

        st.write("")
        # DEFs
        defs = [p for p in starters if p.player and p.player.position == Position.DEF]
        d_cols = st.columns(len(defs) or 1)
        for i, pick in enumerate(defs):
            with d_cols[i]:
                p = pick.player
                status_icon = "🟢" if (p.chance_of_playing is None or p.chance_of_playing == 100) else "🔴"
                capt = " 👑 (C)" if pick.is_captain else (" (VC)" if pick.is_vice_captain else "")
                st.markdown(f"""
                <div class="player-card">
                    <div style="font-weight: 800; font-size: 1.05rem;">{p.web_name}{capt}</div>
                    <div style="font-size: 0.85rem; color: #00ff87;">{p.team_short_name} • £{p.price:.1f}m {status_icon}</div>
                    <div style="font-size: 0.8rem; opacity: 0.8;">Form: {p.form:.1f} • Score: {p.composite_score:.1f}</div>
                </div>
                """, unsafe_allow_html=True)

        st.write("")
        # MIDs
        mids = [p for p in starters if p.player and p.player.position == Position.MID]
        m_cols = st.columns(len(mids) or 1)
        for i, pick in enumerate(mids):
            with m_cols[i]:
                p = pick.player
                status_icon = "🟢" if (p.chance_of_playing is None or p.chance_of_playing == 100) else "🔴"
                capt = " 👑 (C)" if pick.is_captain else (" (VC)" if pick.is_vice_captain else "")
                st.markdown(f"""
                <div class="player-card">
                    <div style="font-weight: 800; font-size: 1.05rem;">{p.web_name}{capt}</div>
                    <div style="font-size: 0.85rem; color: #00ff87;">{p.team_short_name} • £{p.price:.1f}m {status_icon}</div>
                    <div style="font-size: 0.8rem; opacity: 0.8;">Form: {p.form:.1f} • Score: {p.composite_score:.1f}</div>
                </div>
                """, unsafe_allow_html=True)

        st.write("")
        # FWDs
        fwds = [p for p in starters if p.player and p.player.position == Position.FWD]
        f_cols = st.columns(len(fwds) or 1)
        for i, pick in enumerate(fwds):
            with f_cols[i]:
                p = pick.player
                status_icon = "🟢" if (p.chance_of_playing is None or p.chance_of_playing == 100) else "🔴"
                capt = " 👑 (C)" if pick.is_captain else (" (VC)" if pick.is_vice_captain else "")
                st.markdown(f"""
                <div class="player-card">
                    <div style="font-weight: 800; font-size: 1.05rem;">{p.web_name}{capt}</div>
                    <div style="font-size: 0.85rem; color: #00ff87;">{p.team_short_name} • £{p.price:.1f}m {status_icon}</div>
                    <div style="font-size: 0.8rem; opacity: 0.8;">Form: {p.form:.1f} • Score: {p.composite_score:.1f}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # Bench
        st.caption("🪑 Bench Substitutes")
        b_cols = st.columns(len(bench) or 1)
        for i, pick in enumerate(bench):
            with b_cols[i]:
                p = pick.player
                if p:
                    st.markdown(f"""
                    <div style="background: rgba(0,0,0,0.3); border: 1px dashed rgba(255,255,255,0.2); border-radius: 8px; padding: 6px; text-align: center;">
                        <small><strong>{p.web_name}</strong></small><br>
                        <small style="color: #00ff87;">{p.position.label} • £{p.price:.1f}m</small>
                    </div>
                    """, unsafe_allow_html=True)

    with col_analysis:
        st.subheader("🦁 Leo's Player Verdict")
        
        # Player selection dropdown
        player_names = {p.id: f"{p.web_name} ({p.team_short_name} - {p.position.label} - £{p.price:.1f}m)" for p in squad_players}
        selected_pid = st.selectbox(
            "Select a squad player to analyze:",
            options=list(player_names.keys()),
            format_func=lambda x: player_names[x]
        )
        
        target_p = players_by_id[selected_pid]
        
        # Run Deterministic Engine
        verdict = transfer_engine.evaluate_player(target_p, squad_players, active_squad.bank)
        
        # Generate Leo's response
        with st.spinner("Leo is analyzing the numbers..."):
            leo_text = leo_agent.generate_explanation(verdict, f"Should I keep or transfer {target_p.web_name}?")

        st.markdown(f"""
        <div class="verdict-card">
            {st.markdown(leo_text)}
        </div>
        """, unsafe_allow_html=True)

        st.write("")
        # Top Replacements Table
        replacements = transfer_engine.find_best_replacements(target_p, squad_players, active_squad.bank, limit=4)
        if replacements:
            st.markdown("#### 🔄 Top Valid Market Replacements")
            rep_data = []
            for r in replacements:
                fix_str = " • ".join([f.formatted for f in r.upcoming_fixtures[:3]])
                rep_data.append({
                    "Player": r.web_name,
                    "Club": r.team_short_name,
                    "Price": f"£{r.price:.1f}m",
                    "Form": r.form,
                    "xGI/90": f"{r.xgi_per_90:.2f}",
                    "Rating": r.composite_score,
                    "Next 3 Fixtures": fix_str
                })
            st.dataframe(pd.DataFrame(rep_data), use_container_width=True, hide_index=True)

# ----------------- TAB 2: CAPTAINCY SHOWDOWN -----------------
with tab_captain:
    st.subheader("⭐ Gameweek Captaincy Showdown")
    st.write("Deterministic expected points rating based on Form (40%), xGI/90 (35%), and Immediate Fixture Ease (25%).")

    col_cap_recom, col_cap_table = st.columns([1.1, 0.9])

    best_c, best_vc, ranked_squad_captains = captain_engine.select_best_captains(squad_players)
    captain_verdict = captain_engine.evaluate_captaincy(squad_players, best_c)

    with col_cap_recom:
        st.markdown("### 🦁 Leo's Armband Verdict")
        with st.spinner("Leo is running captaincy projections..."):
            cap_leo_text = leo_agent.generate_explanation(captain_verdict, "Who should I captain this gameweek?")
        
        st.markdown(f"""
        <div class="verdict-card">
            {st.markdown(cap_leo_text)}
        </div>
        """, unsafe_allow_html=True)

    with col_cap_table:
        st.markdown("### 📊 Ranked Squad Captaincy Options")
        cap_table_data = []
        for p, score in ranked_squad_captains[:6]:
            next_f = p.upcoming_fixtures[0].formatted if p.upcoming_fixtures else "N/A"
            cap_table_data.append({
                "Player": p.web_name,
                "Team": p.team_short_name,
                "Price": f"£{p.price:.1f}m",
                "Form": p.form,
                "xGI/90": f"{p.xgi_per_90:.2f}",
                "Next Fixture": next_f,
                "Captain Rating": f"{score:.2f}"
            })
        st.dataframe(pd.DataFrame(cap_table_data), use_container_width=True, hide_index=True)

# ----------------- TAB 3: LIVE MARKET & INJURY HOSPITAL -----------------
with tab_market:
    st.subheader("📈 Live FPL Market Pulse & Injury Hospital")
    
    col_risers, col_fallers = st.columns(2)
    
    with col_risers:
        st.markdown("#### 🚀 Top Transfer Momentum (Price Rise Watch)")
        risers = sorted(all_players, key=lambda p: p.transfers_in_event - p.transfers_out_event, reverse=True)[:6]
        r_data = [{
            "Player": p.web_name,
            "Team": p.team_short_name,
            "Price": f"£{p.price:.1f}m",
            "Net In": f"+{(p.transfers_in_event - p.transfers_out_event):,}",
            "Form": p.form,
            "Score": p.composite_score
        } for p in risers]
        st.dataframe(pd.DataFrame(r_data), use_container_width=True, hide_index=True)

    with col_fallers:
        st.markdown("#### 📉 Impending Price Drops (Sell Pressure)")
        fallers = sorted(all_players, key=lambda p: p.transfers_out_event - p.transfers_in_event, reverse=True)[:6]
        f_data = [{
            "Player": p.web_name,
            "Team": p.team_short_name,
            "Price": f"£{p.price:.1f}m",
            "Net Out": f"-{(p.transfers_out_event - p.transfers_in_event):,}",
            "Form": p.form,
            "Score": p.composite_score
        } for p in fallers]
        st.dataframe(pd.DataFrame(f_data), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 🏥 Premier League Injury & Suspension Hospital")
    flagged_players = [p for p in all_players if p.status in ["i", "d", "s", "u"] or (p.chance_of_playing is not None and p.chance_of_playing < 100)]
    flagged_players.sort(key=lambda p: p.selected_by_percent, reverse=True)
    
    h_data = [{
        "Player": p.web_name,
        "Team": p.team_short_name,
        "Ownership": f"{p.selected_by_percent}%",
        "Chance of Playing": f"{p.chance_of_playing if p.chance_of_playing is not None else 0}%",
        "Official Club News": p.news or "Flagged as unavailable"
    } for p in flagged_players[:12]]
    st.dataframe(pd.DataFrame(h_data), use_container_width=True, hide_index=True)

# ----------------- TAB 4: CHAT WITH LEO -----------------
with tab_chat:
    st.subheader("💬 Ask Leo Any FPL Question")
    st.caption("Leo combines live official data with sharp, concise Premier League tactical analysis.")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Welcome to the Pride! I am Leo, your FPL analyst. Ask me about any player, transfer dilemma, captaincy pick, or fixture swing."}
        ]

    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🦁" if msg["role"] == "assistant" else None):
            st.markdown(msg["content"])

    # User input
    if prompt := st.chat_input("e.g. Should I transfer out Saka for Palmer?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Match player in query
        prompt_lower = prompt.lower()
        matched_player = None
        for p in all_players:
            if p.web_name.lower() in prompt_lower or p.second_name.lower() in prompt_lower:
                matched_player = p
                break

        if not matched_player:
            # Default to captaincy or top squad player
            matched_player = squad_players[0]

        verdict = transfer_engine.evaluate_player(matched_player, squad_players, active_squad.bank)
        
        with st.chat_message("assistant", avatar="🦁"):
            with st.spinner("Leo is crunching the numbers..."):
                response_text = leo_agent.generate_explanation(verdict, prompt)
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
