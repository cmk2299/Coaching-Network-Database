#!/usr/bin/env python3
"""
Football Coaches Database - Interactive Dashboard
Search coaches by name or browse by league > club > coach
"""

import json
import sys
import io
import zipfile
from pathlib import Path
from datetime import datetime

# Add execution directory to path
EXEC_DIR = Path(__file__).resolve().parent.parent / "execution"
sys.path.insert(0, str(EXEC_DIR))

import streamlit as st

# Force cache clear on startup to ensure fresh data after deployment
# This ensures Decision Makers data is loaded after GitHub updates
if 'cache_cleared' not in st.session_state:
    st.cache_data.clear()
    st.session_state.cache_cleared = True

from scrape_transfermarkt import scrape_coach, search_coach
from scrape_teammates import scrape_teammates, enrich_teammates_with_current_roles
from scrape_players_used import scrape_players_used
from scrape_league_coaches import scrape_bundesliga_coaches, BUNDESLIGA_CLUBS
from scrape_players_detail import scrape_players_for_coach_url
from scrape_player_agents import enrich_players_with_agents
from scrape_companions import get_companions_for_coach
from license_cohorts import get_cohort_mates, find_cohort_for_coach, get_cohort_info
from preload_coach_data import load_preloaded, PRELOAD_DIR
from scrape_playing_career import scrape_coach_achievements
from get_club_logo import get_club_logo, get_logo_by_id
import re
from streamlit_agraph import agraph, Node, Edge, Config

# Page config
st.set_page_config(
    page_title="Football Coaches DB",
    page_icon="⚽",
    layout="wide"
)

# Version for cache busting
APP_VERSION = "1.1.0"  # Updated: Decision Makers integration

# Custom CSS with P1.3 Mobile Responsive + P2.2 Visual Hierarchy
st.markdown("""
<style>
    /* Typography Hierarchy */
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        color: #1d3557;
    }
    .sub-header {
        color: #666;
        margin-bottom: 2rem;
        font-size: 1.1rem;
    }

    /* Enhanced Stat Cards */
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stat-number {
        font-size: 2rem;
        font-weight: bold;
    }
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }

    /* Card Components */
    .teammate-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        border-left: 4px solid #667eea;
        transition: transform 0.2s;
    }
    .teammate-card:hover {
        transform: translateX(4px);
    }

    /* Badges */
    .coach-badge {
        background: #28a745;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-left: 8px;
    }
    .insight-badge {
        background: #e63946;
        color: white;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85rem;
        font-weight: 500;
    }

    /* Improved Spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stExpander"] {
        background: #f8f9fa;
        border-radius: 8px;
        border: 1px solid #e1e4e8;
    }

    /* Mobile Responsive (P1.3) */
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.8rem;
        }
        .stat-card {
            padding: 1rem;
        }
        .stat-number {
            font-size: 1.5rem;
        }
        div[data-testid="column"] {
            min-width: 100% !important;
            margin-bottom: 1rem;
        }
    }

    /* Tab Improvements for Touch */
    @media (max-width: 768px) {
        button[data-baseweb="tab"] {
            min-height: 48px;
            padding: 12px 16px;
        }
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<p class="main-header">⚽ Football Coaches Database</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Comprehensive coach profiles from Transfermarkt for projectFIVE</p>', unsafe_allow_html=True)

# Initialize session state
if "coach_data" not in st.session_state:
    st.session_state.coach_data = None
if "loading" not in st.session_state:
    st.session_state.loading = False
if "bundesliga_coaches" not in st.session_state:
    st.session_state.bundesliga_coaches = None


@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_bundesliga_coaches():
    """Get current Bundesliga coaches (cached)."""
    return scrape_bundesliga_coaches()


def try_load_preloaded(coach_name: str) -> dict:
    """
    Try to load preloaded data for a coach.
    Returns full data dict if available and fresh (within 7 days), None otherwise.
    """
    try:
        data = load_preloaded(coach_name)
        if data and data.get("profile"):
            # Check freshness (7 days = 168 hours)
            preloaded_at = datetime.fromisoformat(data.get("_preloaded_at", "2000-01-01"))
            age_hours = (datetime.now() - preloaded_at).total_seconds() / 3600

            if age_hours < 168:  # 7 days
                return {
                    "profile": data.get("profile"),
                    "teammates": data.get("teammates"),
                    "players_used": data.get("players_used"),
                    "players_detail": data.get("players_detail"),
                    "companions": data.get("companions"),
                    "decision_makers": data.get("decision_makers"),  # CRITICAL FIX: Was missing!
                    "_preloaded": True,
                    "_preloaded_at": data.get("_preloaded_at"),
                }
    except Exception as e:
        pass  # Fall back to live scraping

    return None


def get_preload_status() -> dict:
    """Get status of preloaded data for all Bundesliga coaches."""
    status = {}

    if not PRELOAD_DIR.exists():
        return status

    for file in PRELOAD_DIR.glob("*.json"):
        try:
            with open(file, "r") as f:
                data = json.load(f)

            coach_name = data.get("_coach_name", file.stem)
            preloaded_at = datetime.fromisoformat(data.get("_preloaded_at", "2000-01-01"))
            age_hours = (datetime.now() - preloaded_at).total_seconds() / 3600

            status[coach_name] = {
                "fresh": age_hours < 168,  # 7 days
                "age_hours": age_hours,
                "teammates_enriched": data.get("teammates_enriched", False),
            }
        except:
            pass

    return status


def generate_full_export(data: dict) -> bytes:
    """
    Generate a ZIP file containing all coach data as CSVs.
    Returns bytes ready for download.
    """
    profile = data.get("profile", {})
    teammates = data.get("teammates", {})
    players_used = data.get("players_used", {})
    players_detail = data.get("players_detail", {})
    companions = data.get("companions", {})

    coach_name = profile.get("name", "coach").replace(" ", "_")

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

        # 1. Profile CSV
        profile_csv = "Field,Value\n"
        profile_csv += f"Name,{profile.get('name', '')}\n"
        profile_csv += f"Nationality,{profile.get('nationality', '')}\n"
        profile_csv += f"Age,{profile.get('age', '')}\n"
        profile_csv += f"Current Club,{profile.get('current_club', '')}\n"
        profile_csv += f"Current Role,{profile.get('current_role', '')}\n"
        profile_csv += f"License,{profile.get('license', '')}\n"
        profile_csv += f"Agent,{profile.get('agent', '')}\n"
        profile_csv += f"TM Profile,{profile.get('url', '')}\n"
        zf.writestr(f"{coach_name}_01_profile.csv", profile_csv)

        # 2. Coaching Stations CSV
        if players_used and players_used.get("stations"):
            stations_csv = "Club,Period,Games,Wins,Draws,Losses,PPG,Players Used\n"
            for s in players_used["stations"]:
                wins = s.get("wins", 0)
                draws = s.get("draws", 0)
                losses = s.get("losses", 0)
                games = wins + draws + losses
                ppg = round((wins * 3 + draws) / games, 2) if games > 0 else 0
                stations_csv += f"\"{s.get('club', '')}\",\"{s.get('period', '')}\",{s.get('games', 0)},{wins},{draws},{losses},{ppg},{s.get('players_used', 0)}\n"
            zf.writestr(f"{coach_name}_02_stations.csv", stations_csv)

        # 3. Network/Contacts CSV (comprehensive)
        network_contacts = []

        # Teammates who became coaches/directors
        if teammates and teammates.get("all_teammates"):
            for tm in teammates["all_teammates"]:
                if tm.get("is_coach") or tm.get("is_director"):
                    role = "Coach" if tm.get("is_coach") else "Director"
                    network_contacts.append({
                        "name": tm.get("name", ""),
                        "role": role,
                        "current_club": tm.get("current_club", ""),
                        "connection": f"Teammate ({tm.get('shared_matches', 0)} games)",
                        "category": "Teammate → Coach/Director",
                        "url": tm.get("trainer_url") or tm.get("url", ""),
                    })

        # Companions
        if companions:
            # Sports directors
            for sd in companions.get("all_sports_directors", []):
                network_contacts.append({
                    "name": sd.get("name", ""),
                    "role": sd.get("role", "Sports Director"),
                    "current_club": sd.get("club_name", ""),
                    "connection": f"Worked together at {sd.get('club_name', '')}",
                    "category": "Sports Director",
                    "url": sd.get("url", ""),
                })

            # Former bosses
            for boss in companions.get("former_bosses", []):
                network_contacts.append({
                    "name": boss.get("name", ""),
                    "role": "Head Coach (former)",
                    "current_club": boss.get("club_name", ""),
                    "connection": f"Was his boss at {boss.get('club_name', '')}",
                    "category": "Former Boss",
                    "url": boss.get("url", ""),
                })

            # Co-trainers
            for ct in companions.get("current_co_trainers", []):
                network_contacts.append({
                    "name": ct.get("name", ""),
                    "role": ct.get("role", "Assistant Coach"),
                    "current_club": profile.get("current_club", ""),
                    "connection": "Current Assistant",
                    "category": "Assistant Coach",
                    "url": ct.get("url", ""),
                })

            # Management
            for mgmt in companions.get("all_management", []):
                network_contacts.append({
                    "name": mgmt.get("name", ""),
                    "role": mgmt.get("role", "Management"),
                    "current_club": mgmt.get("club_name", ""),
                    "connection": f"Management at {mgmt.get('club_name', '')}",
                    "category": "Management",
                    "url": mgmt.get("url", ""),
                })

        # License cohort
        cohort_num = find_cohort_for_coach(profile.get("name", ""))
        if cohort_num:
            for mate in get_cohort_mates(profile.get("name", "")):
                network_contacts.append({
                    "name": mate.get("name", ""),
                    "role": "Coach",
                    "current_club": mate.get("note", ""),
                    "connection": f"Pro License Cohort {cohort_num}",
                    "category": "License Cohort",
                    "url": "",
                })

        if network_contacts:
            network_csv = "Name,Role,Current Club,Connection,Category,TM URL\n"
            for c in network_contacts:
                network_csv += f"\"{c['name']}\",\"{c['role']}\",\"{c['current_club']}\",\"{c['connection']}\",\"{c['category']}\",\"{c['url']}\"\n"
            zf.writestr(f"{coach_name}_03_network.csv", network_csv)

        # 4. Teammates CSV (all)
        if teammates and teammates.get("all_teammates"):
            tm_csv = "Name,Position,Shared Matches,Teams Together,Minutes,Now Coach,Current Club,TM URL\n"
            for tm in teammates["all_teammates"]:
                is_coach = "Yes" if tm.get("is_coach") else "No"
                tm_csv += f"\"{tm.get('name', '')}\",\"{tm.get('position', '')}\",{tm.get('shared_matches', 0)},{tm.get('teams_together', 0)},{tm.get('total_minutes', 0)},{is_coach},\"{tm.get('current_club', '')}\",\"{tm.get('url', '')}\"\n"
            zf.writestr(f"{coach_name}_04_teammates.csv", tm_csv)

        # 5. Players Coached CSV
        if players_detail and players_detail.get("players"):
            players_csv = "Rank,Name,Position,Age,Appearances,Minutes,Goals,Assists,Market Value,Agent,Contract Until,TM URL\n"
            for i, p in enumerate(players_detail["players"], 1):
                players_csv += f"{i},\"{p.get('name', '')}\",\"{p.get('position', '')}\",{p.get('age', '')},{p.get('appearances', 0)},{p.get('minutes', 0)},{p.get('goals', 0)},{p.get('assists', 0)},\"{p.get('market_value', '-')}\",\"{p.get('agent', '-')}\",\"{p.get('contract_until', '-')}\",\"{p.get('url', '')}\"\n"
            zf.writestr(f"{coach_name}_05_players_coached.csv", players_csv)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


# Sidebar for search options
with st.sidebar:
    st.header("🔍 Search Options")

    search_method = st.radio(
        "Search Method",
        ["Direct Search", "Browse by League", "🔄 Reverse Lookup", "⚖️ Compare Coaches"],
        index=0
    )

    if search_method == "Direct Search":
        # P0.3: Better Search UX with examples
        st.caption("💡 Try: **Xabi Alonso**, **Vincent Kompany**, **Nuri Şahin**")
        coach_name = st.text_input(
            "Coach Name",
            placeholder="e.g. Alexander Blessin",
            help="Enter coach name - autocomplete coming soon!"
        )
        search_button = st.button("🔍 Search Coach", type="primary", use_container_width=True)

        if search_button and coach_name:
            st.session_state.loading = True
            st.session_state.search_name = coach_name

    elif search_method == "Browse by League":
        st.subheader("📊 League Filter")

        league = st.selectbox("League", ["Bundesliga"])

        club = st.selectbox(
            "Club",
            ["Select a club..."] + sorted(list(BUNDESLIGA_CLUBS.keys()))
        )

        if club != "Select a club...":
            # Try to get current coach from cache
            if st.session_state.bundesliga_coaches:
                club_info = st.session_state.bundesliga_coaches.get("clubs", {}).get(club, {})
                current_coach = club_info.get("coach_name", "Unknown")
                st.success(f"**{club}**\nCurrent coach: **{current_coach}**")
            else:
                st.info(f"**{club}**\nClick below to find current coach")

            browse_button = st.button("🔍 Load Coach Profile", type="primary", use_container_width=True)

            if browse_button:
                st.session_state.loading = True
                st.session_state.browse_club = club

    elif search_method == "🔄 Reverse Lookup":
        st.subheader("🔄 Reverse Lookup")
        st.markdown("*Find all coaches who know a specific person*")

        reverse_search_name = st.text_input("Search person", placeholder="e.g. Marcel Rapp")
        reverse_search_btn = st.button("🔍 Find connections", type="primary", use_container_width=True)

        if reverse_search_btn and reverse_search_name:
            st.session_state.reverse_search = reverse_search_name

    else:  # Compare Coaches
        st.subheader("⚖️ Compare Coaches")
        st.markdown("*Compare 2-3 coaches side by side*")

        # Get list of preloaded coaches
        available_coaches = []
        if PRELOAD_DIR.exists():
            for file in PRELOAD_DIR.glob("*.json"):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    coach_name = data.get("_coach_name", file.stem)
                    available_coaches.append(coach_name)
                except:
                    pass

        if available_coaches:
            available_coaches = sorted(available_coaches)

            coach1 = st.selectbox("Coach 1", ["Select..."] + available_coaches, key="compare_coach1")
            coach2 = st.selectbox("Coach 2", ["Select..."] + available_coaches, key="compare_coach2")
            coach3 = st.selectbox("Coach 3 (optional)", ["None"] + available_coaches, key="compare_coach3")

            if coach1 != "Select..." and coach2 != "Select...":
                if st.button("⚖️ Compare", type="primary", use_container_width=True):
                    coaches_to_compare = [coach1, coach2]
                    if coach3 != "None":
                        coaches_to_compare.append(coach3)
                    st.session_state.compare_coaches = coaches_to_compare
        else:
            st.warning("No preloaded data available. Run preloading first.")

    # Refresh button for league data
    st.divider()
    if st.button("🔄 Refresh League Data", use_container_width=True):
        st.session_state.bundesliga_coaches = None
        st.cache_data.clear()
        st.rerun()

    # Export button (only show if coach data is loaded)
    if st.session_state.coach_data:
        st.divider()
        st.header("📥 Export")

        coach_name_export = st.session_state.coach_data.get("profile", {}).get("name", "coach")
        timestamp = datetime.now().strftime("%Y%m%d")

        zip_data = generate_full_export(st.session_state.coach_data)

        st.download_button(
            "📥 Full Export (ZIP)",
            data=zip_data,
            file_name=f"{coach_name_export.replace(' ', '_')}_{timestamp}_export.zip",
            mime="application/zip",
            use_container_width=True,
            help="Exports all data as ZIP with multiple CSVs: Profile, Stations, Network, Teammates, Players"
        )

        st.caption("Contains: Profile, Stations (with PPG), Network, Teammates, Players Coached")


# Load Bundesliga coaches in background
if st.session_state.bundesliga_coaches is None:
    with st.spinner("Loading Bundesliga coaches..."):
        try:
            st.session_state.bundesliga_coaches = get_bundesliga_coaches()
        except Exception as e:
            st.warning(f"Could not load league data: {e}")


# Handle Reverse Lookup
if hasattr(st.session_state, "reverse_search") and st.session_state.reverse_search:
    search_term = st.session_state.reverse_search.lower()
    del st.session_state.reverse_search

    st.markdown(f"## 🔄 Reverse Lookup: *{search_term.title()}*")
    st.markdown("*Searching all preloaded coach data for connections...*")

    connections_found = []

    # Search through all preloaded data
    if PRELOAD_DIR.exists():
        preload_files = list(PRELOAD_DIR.glob("*.json"))

        if not preload_files:
            st.warning("No preloaded data found. Run preloading first.")
        else:
            progress = st.progress(0, text="Searching coach data...")

            for i, file in enumerate(preload_files):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        coach_data = json.load(f)

                    coach_name = coach_data.get("_coach_name", file.stem)
                    progress.progress((i + 1) / len(preload_files), text=f"Checking {coach_name}...")

                    # Search in teammates
                    teammates = coach_data.get("teammates", {})
                    if teammates and teammates.get("all_teammates"):
                        for tm in teammates["all_teammates"]:
                            if search_term in tm.get("name", "").lower():
                                connections_found.append({
                                    "coach": coach_name,
                                    "person": tm.get("name", ""),
                                    "connection_type": "Teammate",
                                    "details": f"{tm.get('shared_matches', 0)} shared matches",
                                    "is_now_coach": tm.get("is_coach", False),
                                    "current_club": tm.get("current_club", ""),
                                })

                    # Search in companions
                    companions = coach_data.get("companions", {})
                    if companions:
                        # Sports Directors
                        for sd in companions.get("all_sports_directors", []):
                            if search_term in sd.get("name", "").lower():
                                connections_found.append({
                                    "coach": coach_name,
                                    "person": sd.get("name", ""),
                                    "connection_type": "Sports Director",
                                    "details": f"At {sd.get('club_name', '')}",
                                    "is_now_coach": False,
                                    "current_club": sd.get("club_name", ""),
                                })

                        # Former bosses
                        for boss in companions.get("former_bosses", []):
                            if search_term in boss.get("name", "").lower():
                                connections_found.append({
                                    "coach": coach_name,
                                    "person": boss.get("name", ""),
                                    "connection_type": "Former Boss",
                                    "details": f"At {boss.get('club_name', '')}",
                                    "is_now_coach": True,
                                    "current_club": boss.get("club_name", ""),
                                })

                        # Co-trainers
                        for ct in companions.get("current_co_trainers", []):
                            if search_term in ct.get("name", "").lower():
                                connections_found.append({
                                    "coach": coach_name,
                                    "person": ct.get("name", ""),
                                    "connection_type": "Assistant Coach",
                                    "details": ct.get("role", ""),
                                    "is_now_coach": True,
                                    "current_club": "",
                                })

                        # Management
                        for mgmt in companions.get("all_management", []):
                            if search_term in mgmt.get("name", "").lower():
                                connections_found.append({
                                    "coach": coach_name,
                                    "person": mgmt.get("name", ""),
                                    "connection_type": "Management",
                                    "details": f"{mgmt.get('role', '')} at {mgmt.get('club_name', '')}",
                                    "is_now_coach": False,
                                    "current_club": mgmt.get("club_name", ""),
                                })

                    # Search in players coached
                    players_detail = coach_data.get("players_detail", {})
                    if players_detail and players_detail.get("players"):
                        for player in players_detail["players"]:
                            if search_term in player.get("name", "").lower():
                                connections_found.append({
                                    "coach": coach_name,
                                    "person": player.get("name", ""),
                                    "connection_type": "Player Coached",
                                    "details": f"{player.get('appearances', 0)} apps, {player.get('minutes', 0)} min",
                                    "is_now_coach": False,
                                    "current_club": "",
                                })

                except Exception as e:
                    continue

            progress.progress(1.0, text="Done!")

            # Display results
            if connections_found:
                st.success(f"**{len(connections_found)} connections found!**")

                # Group by coach
                coaches_with_connection = {}
                for conn in connections_found:
                    coach = conn["coach"]
                    if coach not in coaches_with_connection:
                        coaches_with_connection[coach] = []
                    coaches_with_connection[coach].append(conn)

                st.markdown(f"### {len(coaches_with_connection)} coaches know *{search_term.title()}*:")

                # Display as expandable sections
                for coach, conns in coaches_with_connection.items():
                    with st.expander(f"**{coach}** ({len(conns)} connection{'s' if len(conns) > 1 else ''})"):
                        for conn in conns:
                            st.markdown(f"""
                            - **{conn['connection_type']}**: {conn['person']}
                              - {conn['details']}
                            """)

                # Also show as table
                st.divider()
                st.markdown("### All Connections as Table")

                table_data = []
                for conn in connections_found:
                    table_data.append({
                        "Coach": conn["coach"],
                        "Connection to": conn["person"],
                        "Type": conn["connection_type"],
                        "Details": conn["details"],
                    })

                st.dataframe(
                    table_data,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Coach": st.column_config.TextColumn(width="medium"),
                        "Connection to": st.column_config.TextColumn(width="medium"),
                        "Type": st.column_config.TextColumn(width="small"),
                        "Details": st.column_config.TextColumn(width="large"),
                    }
                )

                # Download
                csv_data = "Coach,Connection to,Type,Details\n"
                for conn in connections_found:
                    csv_data += f"{conn['coach']},{conn['person']},{conn['connection_type']},{conn['details']}\n"

                st.download_button(
                    "📥 Export Results as CSV",
                    data=csv_data,
                    file_name=f"reverse_lookup_{search_term.replace(' ', '_')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning(f"No connections to '{search_term}' found in the preloaded data.")
                st.info("Tip: Make sure the Bundesliga coaches have been preloaded.")
    else:
        st.warning("Preload directory not found. Run preloading first.")

    st.stop()  # Don't show normal dashboard content


# Handle Compare Coaches
if hasattr(st.session_state, "compare_coaches") and st.session_state.compare_coaches:
    coaches_to_compare = st.session_state.compare_coaches
    del st.session_state.compare_coaches

    st.markdown(f"## ⚖️ Coach Comparison")

    # Load data for all coaches
    coach_data_list = []
    for coach_name in coaches_to_compare:
        data = try_load_preloaded(coach_name)
        if data:
            coach_data_list.append(data)
        else:
            st.warning(f"Could not load data for {coach_name}")

    if len(coach_data_list) >= 2:
        # Create columns for comparison
        cols = st.columns(len(coach_data_list))

        # Profile comparison
        for i, (col, data) in enumerate(zip(cols, coach_data_list)):
            profile = data.get("profile", {})
            players_used = data.get("players_used", {})
            teammates = data.get("teammates", {})

            # Calculate stats
            total_games = players_used.get("total_games", 0) if players_used else 0
            stations_count = players_used.get("stations_count", 0) if players_used else 0

            career_ppg = 0
            if players_used and players_used.get("stations"):
                total_wins = sum(s.get("wins", 0) for s in players_used["stations"])
                total_draws = sum(s.get("draws", 0) for s in players_used["stations"])
                total_losses = sum(s.get("losses", 0) for s in players_used["stations"])
                total_games_calc = total_wins + total_draws + total_losses
                career_ppg = (total_wins * 3 + total_draws) / total_games_calc if total_games_calc > 0 else 0

            with col:
                # Profile image and name
                if profile.get("image_url"):
                    st.image(profile["image_url"], width=120)
                st.markdown(f"### {profile.get('name', 'Unknown')}")
                st.caption(f"{profile.get('current_role', 'Coach')} @ {profile.get('current_club', '?')}")

                st.divider()

                # Key stats
                st.metric("Career PPG", f"{career_ppg:.2f}")
                st.metric("Total Games", total_games)
                st.metric("Stations", stations_count)
                st.metric("Teammates", len(teammates.get("all_teammates", [])) if teammates else 0)

                st.divider()

                # Profile details
                st.markdown(f"**Age:** {profile.get('age', 'N/A')}")
                st.markdown(f"**Nationality:** {profile.get('nationality', 'N/A')}")
                st.markdown(f"**License:** {profile.get('license', 'N/A')}")
                st.markdown(f"**Agent:** {profile.get('agent', 'N/A')}")

        st.divider()

        # Detailed comparison table
        st.markdown("### 📊 Side-by-Side Statistics")

        comparison_rows = [
            ("Age", [d.get("profile", {}).get("age", "N/A") for d in coach_data_list]),
            ("Nationality", [d.get("profile", {}).get("nationality", "N/A") for d in coach_data_list]),
            ("License", [d.get("profile", {}).get("license", "N/A") for d in coach_data_list]),
            ("Current Club", [d.get("profile", {}).get("current_club", "N/A") for d in coach_data_list]),
            ("Total Games", [d.get("players_used", {}).get("total_games", 0) if d.get("players_used") else 0 for d in coach_data_list]),
            ("Stations", [d.get("players_used", {}).get("stations_count", 0) if d.get("players_used") else 0 for d in coach_data_list]),
            ("Career PPG", []),  # Calculated below
            ("Win Rate", []),    # Calculated below
            ("Teammates", [len(d.get("teammates", {}).get("all_teammates", [])) if d.get("teammates") else 0 for d in coach_data_list]),
            ("Players Coached", [len(d.get("players_detail", {}).get("players", [])) if d.get("players_detail") else 0 for d in coach_data_list]),
        ]

        # Calculate PPG and Win Rate
        ppg_values = []
        winrate_values = []
        for data in coach_data_list:
            players_used = data.get("players_used", {})
            if players_used and players_used.get("stations"):
                total_wins = sum(s.get("wins", 0) for s in players_used["stations"])
                total_draws = sum(s.get("draws", 0) for s in players_used["stations"])
                total_losses = sum(s.get("losses", 0) for s in players_used["stations"])
                total_games_calc = total_wins + total_draws + total_losses
                ppg = (total_wins * 3 + total_draws) / total_games_calc if total_games_calc > 0 else 0
                winrate = (total_wins / total_games_calc * 100) if total_games_calc > 0 else 0
                ppg_values.append(f"{ppg:.2f}")
                winrate_values.append(f"{winrate:.1f}%")
            else:
                ppg_values.append("N/A")
                winrate_values.append("N/A")

        comparison_rows[6] = ("Career PPG", ppg_values)
        comparison_rows[7] = ("Win Rate", winrate_values)

        # Build comparison table
        table_data = {"Metric": [r[0] for r in comparison_rows]}
        for i, data in enumerate(coach_data_list):
            coach_name = data.get("profile", {}).get("name", f"Coach {i+1}")
            table_data[coach_name] = [r[1][i] for r in comparison_rows]

        import pandas as pd
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Common connections
        st.divider()
        st.markdown("### 🔗 Common Network Connections")

        # Find common teammates
        all_teammate_sets = []
        for data in coach_data_list:
            teammates = data.get("teammates", {})
            if teammates and teammates.get("all_teammates"):
                names = set(tm.get("name", "").lower() for tm in teammates["all_teammates"])
                all_teammate_sets.append(names)
            else:
                all_teammate_sets.append(set())

        if len(all_teammate_sets) >= 2 and all(s for s in all_teammate_sets):
            common = all_teammate_sets[0]
            for s in all_teammate_sets[1:]:
                common = common.intersection(s)

            if common:
                st.success(f"**{len(common)} common teammates found!**")
                st.markdown(", ".join(sorted([n.title() for n in common])))
            else:
                st.info("No common teammates found")
        else:
            st.info("Teammate data not available for comparison")

    else:
        st.error("Need at least 2 coaches to compare")

    st.stop()


# Main content area
if st.session_state.loading:
    with st.spinner("Fetching coach data from Transfermarkt..."):
        try:
            # Direct search
            if hasattr(st.session_state, "search_name") and st.session_state.search_name:
                search_name = st.session_state.search_name

                # TRY PRELOADED DATA FIRST (instant load!)
                preloaded = try_load_preloaded(search_name)
                if preloaded:
                    st.session_state.coach_data = preloaded
                    st.toast(f"⚡ Using preloaded data!", icon="⚡")
                else:
                    # Fall back to live scraping
                    profile = scrape_coach(name=search_name)
                    if profile:
                        coach_url = profile.get("url", "")
                        teammates = scrape_teammates(coach_profile_url=coach_url) if coach_url else None
                        players_used = scrape_players_used(coach_profile_url=coach_url) if coach_url else None
                        players_detail = scrape_players_for_coach_url(coach_url, top_n=None) if coach_url else None

                        st.session_state.coach_data = {
                            "profile": profile,
                            "teammates": teammates,
                            "players_used": players_used,
                            "players_detail": players_detail
                        }
                    else:
                        st.error(f"Coach '{search_name}' not found")
                        st.session_state.coach_data = None

                del st.session_state.search_name

            # Browse by club - fetch current coach dynamically
            elif hasattr(st.session_state, "browse_club") and st.session_state.browse_club:
                club_name = st.session_state.browse_club

                # Get coach from cached league data
                coach_name = None
                if st.session_state.bundesliga_coaches:
                    club_info = st.session_state.bundesliga_coaches.get("clubs", {}).get(club_name, {})
                    coach_name = club_info.get("coach_name")

                if coach_name:
                    # TRY PRELOADED DATA FIRST (instant load!)
                    preloaded = try_load_preloaded(coach_name)
                    if preloaded:
                        st.session_state.coach_data = preloaded
                        st.toast(f"⚡ Using preloaded data!", icon="⚡")
                    else:
                        # Fall back to live scraping
                        profile = scrape_coach(name=coach_name)
                        if profile:
                            coach_url = profile.get("url", "")
                            teammates = scrape_teammates(coach_profile_url=coach_url) if coach_url else None
                            players_used = scrape_players_used(coach_profile_url=coach_url) if coach_url else None
                            players_detail = scrape_players_for_coach_url(coach_url, top_n=None) if coach_url else None

                            st.session_state.coach_data = {
                                "profile": profile,
                                "teammates": teammates,
                                "players_used": players_used,
                                "players_detail": players_detail
                            }
                        else:
                            st.error(f"Could not load profile for {coach_name}")
                            st.session_state.coach_data = None
                else:
                    st.warning(f"Coach for {club_name} not found. Try refreshing league data or direct search.")
                    st.session_state.coach_data = None

                del st.session_state.browse_club

        except Exception as e:
            st.error(f"Error fetching data: {e}")
            import traceback
            st.code(traceback.format_exc())
            st.session_state.coach_data = None

        st.session_state.loading = False
        st.rerun()

# Display coach data
if st.session_state.coach_data:
    data = st.session_state.coach_data
    profile = data.get("profile", {})
    teammates = data.get("teammates", {})
    players_used = data.get("players_used", {})

    # Calculate key stats for header
    total_games = players_used.get("total_games", 0) if players_used else 0
    stations_count = players_used.get("stations_count", 0) if players_used else 0
    if stations_count == 0 and players_used:
        stations_count = players_used.get("clubs_coached", 0)

    # Calculate career PPG for header
    career_ppg = 0
    if players_used and players_used.get("stations"):
        total_wins = sum(s.get("wins", 0) for s in players_used["stations"])
        total_draws = sum(s.get("draws", 0) for s in players_used["stations"])
        total_losses = sum(s.get("losses", 0) for s in players_used["stations"])
        total_games_calc = total_wins + total_draws + total_losses
        career_ppg = (total_wins * 3 + total_draws) / total_games_calc if total_games_calc > 0 else 0

    # Preload indicator with refresh button
    preload_col1, preload_col2 = st.columns([4, 1])
    with preload_col1:
        if data.get("_preloaded"):
            preloaded_at = data.get("_preloaded_at", "")
            if preloaded_at:
                try:
                    preload_time = datetime.fromisoformat(preloaded_at)
                    age_hours = (datetime.now() - preload_time).total_seconds() / 3600
                    age_days = age_hours / 24

                    if age_days > 3:
                        st.warning(f"⚠️ **Data is {age_days:.0f} days old** - Consider refreshing")
                    else:
                        st.success(f"⚡ **Preloaded Data** (updated {age_hours:.0f}h ago)")
                except:
                    st.success(f"⚡ **Preloaded Data**")
    with preload_col2:
        if data.get("_preloaded"):
            if st.button("🔄 Refresh", help="Reload fresh data from Transfermarkt", key="refresh_coach_data"):
                # Clear preloaded flag to force fresh scrape
                coach_name = profile.get("name", "")
                if coach_name:
                    st.session_state.loading = True
                    st.session_state.search_name = coach_name
                    st.session_state.coach_data = None
                    st.rerun()

    # Profile Header with native Streamlit components
    header_col1, header_col2 = st.columns([1, 4])

    with header_col1:
        if profile.get("image_url"):
            st.image(profile["image_url"], width=150)

    with header_col2:
        st.markdown(f"## {profile.get('name', 'Unknown Coach')}")

        # Club logo and role
        club_name = profile.get('current_club', 'Unknown')
        club_url = profile.get('club_url', '')

        # Extract club ID for logo
        club_logo_html = ""
        if club_url:
            import re
            club_id_match = re.search(r'/verein/(\d+)', club_url)
            if club_id_match:
                club_id = club_id_match.group(1)
                logo_url = f"https://tmssl.akamaized.net/images/wappen/head/{club_id}.png"
                club_logo_html = f'<img src="{logo_url}" width="24" style="vertical-align: middle; margin-right: 8px;">'

        st.markdown(f"{club_logo_html}**{profile.get('current_role', 'Coach')}** @ **{club_name}**", unsafe_allow_html=True)

        # Info chips
        info_parts = [
            f"🌍 {profile.get('nationality', 'N/A')}",
            f"📅 Age {profile.get('age', 'N/A')}",
            f"📜 {profile.get('license', 'N/A')}",
            f"👔 {profile.get('agent', 'N/A')}",
        ]
        if profile.get('contract_until'):
            info_parts.append(f"📝 Contract: {profile.get('contract_until')}")

        st.markdown(" &nbsp;•&nbsp; ".join(info_parts))

        # Links
        link_parts = []
        if profile.get('url'):
            link_parts.append(f"[🔗 Transfermarkt]({profile['url']})")
        if profile.get('agent_url'):
            link_parts.append(f"[👔 Agent Profile]({profile['agent_url']})")
        if link_parts:
            st.markdown(" &nbsp;|&nbsp; ".join(link_parts))

    # Key Stats Row with Context (P0.2)
    st.divider()
    stat_cols = st.columns(4)

    with stat_cols[0]:
        st.metric("🎮 Total Games", total_games)
    with stat_cols[1]:
        # Add context for PPG
        ppg_context = ""
        if career_ppg >= 2.0:
            ppg_context = "⭐ Excellent"
        elif career_ppg >= 1.6:
            ppg_context = "📈 Above Average"
        elif career_ppg >= 1.3:
            ppg_context = "➡️ Average"
        else:
            ppg_context = "📉 Below Average"
        st.metric("📊 Career PPG", f"{career_ppg:.2f}", delta=ppg_context)
    with stat_cols[2]:
        st.metric("🏟️ Stations", stations_count)
    with stat_cols[3]:
        teammates_count = len(teammates.get('all_teammates', [])) if teammates else 0
        # Add context for network size
        network_context = "Large" if teammates_count > 100 else ("Medium" if teammates_count > 50 else "Small")
        st.metric("👥 Teammates", teammates_count, delta=f"{network_context} Network")

    # P1.2: Enhanced Key Insights Section with Sports Directors & Contract
    st.divider()
    with st.expander("💡 **Key Insights & Highlights**", expanded=True):
        insights = []

        # Career path insight
        if players_used and players_used.get("stations"):
            stations = players_used["stations"]
            if len(stations) > 3:
                first_club = stations[-1].get("club", "Unknown")
                current_club = stations[0].get("club", profile.get("current_club", "Unknown"))
                insights.append(f"📈 **Career Progression**: Started at {first_club}, now at {current_club} ({len(stations)} stations)")

        # Decision Makers worked with (from enriched data - preferred source)
        decision_makers_data = data.get("decision_makers")


        if decision_makers_data:
            from collections import Counter

            hiring_managers = decision_makers_data.get("hiring_managers", [])
            sports_directors = decision_makers_data.get("sports_directors", [])

            if hiring_managers:
                # Analyze hiring patterns efficiently
                hiring_count = Counter(hm.get("name", "Unknown") for hm in hiring_managers)
                repeat_hirers = {name: count for name, count in hiring_count.items() if count > 1}

                if repeat_hirers:
                    # Show pattern: "Hired Nx times"
                    top_hirer, top_count = max(repeat_hirers.items(), key=lambda x: x[1])
                    insights.append(f"🎯 **Hired {len(hiring_managers)}x** across career • Pattern: {top_count}x by **{top_hirer}**")
                else:
                    # Show most recent hiring
                    hm_name = hiring_managers[0].get("name", "Unknown")
                    hm_club = hiring_managers[0].get("club_name", "")
                    insights.append(f"🎯 **Most recent**: Hired by {hm_name} at {hm_club}")

            if sports_directors:
                # Find strong ties efficiently
                sd_names = [sd.get("name", "") for sd in sports_directors]
                unique_sds = len(set(sd_names))
                total_sds = len(sports_directors)

                if unique_sds < total_sds:
                    insights.append(f"📋 **{unique_sds} Sports Directors** in network • Strong ties with key decision makers")
                else:
                    insights.append(f"📋 **{total_sds} Sports Directors** in network")
        else:
            # Fallback to companions data if decision_makers not available
            companions_data = data.get("companions")
            if companions_data:
                current_sd = companions_data.get("current_sports_director")
                all_sds = companions_data.get("all_sports_directors", [])
                if current_sd:
                    sd_name = current_sd.get("name", "Unknown")
                    insights.append(f"🤝 **Current Sports Director**: {sd_name} at {profile.get('current_club', '')}")
                if len(all_sds) > 1:
                    insights.append(f"📋 **Network**: Worked with {len(all_sds)} different Sports Directors in career")

        # Contract duration (if available from profile)
        if profile.get("contract_until"):
            insights.append(f"📝 **Contract**: Until {profile.get('contract_until')}")
        elif profile.get("contract_expires"):
            insights.append(f"📝 **Contract**: Expires {profile.get('contract_expires')}")

        # Network connections from teammates
        if teammates:
            coaches_in_network = sum(1 for tm in teammates.get('all_teammates', []) if tm.get('is_coach'))
            directors_in_network = sum(1 for tm in teammates.get('all_teammates', []) if tm.get('is_director'))
            if coaches_in_network > 0 or directors_in_network > 0:
                insights.append(f"🔗 **Teammate Network**: {coaches_in_network} now coaches, {directors_in_network} directors")

        # Performance insight
        if career_ppg >= 1.6:
            insights.append(f"⭐ **Performance**: {career_ppg:.2f} PPG (Above league average of ~1.45)")
        elif career_ppg > 0:
            context = "Average" if career_ppg >= 1.3 else "Below Average"
            insights.append(f"📊 **Performance**: {career_ppg:.2f} PPG ({context})")

        # Display insights
        if insights:
            for insight in insights:
                st.markdown(f"• {insight}")
        else:
            st.info("💡 Load full profile data to see insights (click 'Load Companions' in Companions tab)")

    # Tabs for detailed info
    tab_dm, tab_network, tab_career, tab_performance = st.tabs([
        "🎯 Decision Makers",
        "🕸️ Complete Network",
        "📋 Career Overview",
        "⚽ Performance"
    ])

    # ===== TAB 1: DECISION MAKERS (NEW!) =====
    with tab_dm:
        st.subheader("Decision Makers Timeline")
        st.caption("Who hired this coach? When and where? This is the intelligence edge.")

        decision_makers_data = data.get("decision_makers")

        if not decision_makers_data or decision_makers_data.get("total", 0) == 0:
            st.info("💡 No decision maker data available yet. This coach's hiring managers will be enriched soon.")
        else:
            # Extract data once (avoid repeated .get() calls)
            hiring_managers = decision_makers_data.get("hiring_managers", [])
            sports_directors = decision_makers_data.get("sports_directors", [])
            executives = decision_makers_data.get("executives", [])
            presidents = decision_makers_data.get("presidents", [])

            # Summary Cards
            col1, col2, col3, col4 = st.columns(4)

            col1.metric("🎯 Hiring Managers", len(hiring_managers))
            col2.metric("📋 Sports Directors", len(sports_directors))
            col3.metric("💼 Executives", len(executives) + len(presidents))

            # Calculate career span efficiently
            profile = data.get("profile", {})
            career_history = profile.get("career_history", [])
            career_span = "N/A"
            if career_history:
                years = []
                for entry in career_history:
                    period = entry.get("period", "")
                    if not period or not period[0].isdigit():
                        continue
                    # Handle different formats: "2024-2025", "2024-present", "0,97" (invalid)
                    if "-" in period:
                        year_str = period.split("-")[0]
                        try:
                            years.append(int(year_str))
                        except ValueError:
                            continue
                if years:
                    career_span = f"{min(years)}-{max(years)}"
            col4.metric("📅 Career Span", career_span)

            st.divider()

            # TIMELINE VIEW
            if hiring_managers:
                st.markdown("### 📅 Hiring Timeline")
                st.caption("Chronological view of who hired this coach at each club")

                # Build timeline from hiring_managers data directly
                # (career_history may have scraping issues with empty clubs)
                timeline_events = []
                for hm in hiring_managers:
                    club = hm.get("club_name", "Unknown Club")
                    period = hm.get("period", "Unknown")

                    timeline_events.append({
                        "period": period,
                        "club": club,
                        "position": "Trainer",  # Default, could be enhanced
                        "hired_by": hm.get("name", "Unknown"),
                        "hired_by_role": hm.get("role", ""),
                        "notes": hm.get("notes", "")
                    })

                # Sort by period (most recent first)
                # Handle different period formats: "2024-present" vs "2022"
                def sort_key(event):
                    p = event["period"]
                    if not p or p == "Unknown":
                        return 0
                    # Extract first year
                    if "-" in p:
                        year_part = p.split("-")[0]
                    else:
                        year_part = p
                    try:
                        return int(year_part)
                    except:
                        return 0

                timeline_events.sort(key=sort_key, reverse=True)

                # Display timeline
                for idx, event in enumerate(timeline_events):
                    with st.container():
                        col_logo, col_year, col_details = st.columns([0.5, 1, 3.5])

                        # Club logo
                        club_logo = get_club_logo(event['club'])
                        if club_logo:
                            col_logo.image(club_logo, width=40)

                        col_year.markdown(f"**{event['period'] or 'Unknown'}**")

                        with col_details:
                            st.markdown(f"**🏟️ {event['club']}** · {event['position']}")
                            st.markdown(f"🎯 Hired by: **{event['hired_by']}** ({event['hired_by_role']})")
                            if event['notes']:
                                st.caption(event['notes'])

                        if idx < len(timeline_events) - 1:
                            st.markdown("↓")

            # PATTERN RECOGNITION (only show if we have hiring managers)
            if hiring_managers:
                st.divider()
                st.markdown("### 🔥 Hiring Patterns")

                # Analyze patterns efficiently with Counter
                from collections import Counter, defaultdict

                hiring_count = Counter(hm.get("name", "Unknown") for hm in hiring_managers)
                repeat_hirers = {name: count for name, count in hiring_count.items() if count > 1}

                if repeat_hirers:
                    st.success("🔁 **Repeat Hiring Relationships Found!**")
                    # Build clubs dict once
                    clubs_by_hirer = defaultdict(list)
                    for hm in hiring_managers:
                        clubs_by_hirer[hm.get("name", "Unknown")].append(hm.get("club_name", ""))

                    for name, count in sorted(repeat_hirers.items(), key=lambda x: -x[1]):
                        st.markdown(f"- **{name}**: Hired {count}x ({', '.join(clubs_by_hirer[name])})")
                else:
                    st.info("No repeat hiring patterns detected. Each hiring manager hired this coach once.")

            st.divider()

            # BY ROLE: Expandable cards
            st.markdown("### 💼 Decision Makers by Role")

            # Helper function to render decision maker cards (DRY principle)
            def render_dm_cards(dm_list, default_role="Unknown"):
                """Render decision maker cards efficiently"""
                for dm in dm_list:
                    st.markdown(f"**{dm.get('name', 'Unknown')}** - {dm.get('role', default_role)}")
                    st.caption(f"📍 {dm.get('club_name', '')}")
                    if dm.get('notes'):
                        st.caption(f"ℹ️ {dm['notes']}")
                    if dm.get('url'):
                        st.caption(f"[Transfermarkt Profile]({dm['url']})")
                    st.markdown("---")

            # Hiring Managers
            if hiring_managers:
                with st.expander(f"🎯 Hiring Managers ({len(hiring_managers)})", expanded=True):
                    render_dm_cards(hiring_managers, "Hiring Manager")

            # Sports Directors
            if sports_directors:
                with st.expander(f"📋 Sports Directors ({len(sports_directors)})", expanded=False):
                    render_dm_cards(sports_directors, "Sports Director")

            # Executives & Presidents
            all_executives = executives + presidents
            if all_executives:
                with st.expander(f"💼 Executives & Presidents ({len(all_executives)})", expanded=False):
                    render_dm_cards(all_executives, "Executive")

    # ===== TAB 2: COMPLETE NETWORK =====
    with tab_network:
        # Collect all network contacts
        network_contacts = []

        # 0. Decision Makers (Hiring Managers, Sports Directors, Executives - from enriched data)
        decision_makers_data = data.get("decision_makers")
        if decision_makers_data:
            # Hiring Managers (most important - who hired this coach)
            for hm in decision_makers_data.get("hiring_managers", []):
                network_contacts.append({
                    "name": hm.get("name", ""),
                    "role": f"🎯 {hm.get('role', 'Hiring Manager')}",
                    "current_club": hm.get("club_name", ""),
                    "connection": hm.get("notes", "Hired this coach"),
                    "url": hm.get("url", ""),
                    "category": "🎯 Hiring Managers",
                    "category_order": 0,
                    "strength": 150,
                })

            # Sports Directors worked with
            for sd in decision_makers_data.get("sports_directors", []):
                # Skip if already added as hiring manager
                if sd.get("name") not in [hm.get("name") for hm in decision_makers_data.get("hiring_managers", [])]:
                    network_contacts.append({
                        "name": sd.get("name", ""),
                        "role": sd.get("role", "Sports Director"),
                        "current_club": sd.get("club_name", ""),
                        "connection": f"At {sd.get('club_name', '')}",
                        "url": sd.get("url", ""),
                        "category": "Sports Directors",
                        "category_order": 1,
                        "strength": 100,
                    })

            # Executives (CEOs, Presidents)
            for exec in decision_makers_data.get("executives", []) + decision_makers_data.get("presidents", []):
                network_contacts.append({
                    "name": exec.get("name", ""),
                    "role": exec.get("role", "Executive"),
                    "current_club": exec.get("club_name", ""),
                    "connection": f"At {exec.get('club_name', '')}",
                    "url": exec.get("url", ""),
                    "category": "Executives",
                    "category_order": 2,
                    "strength": 80,
                })

        # 1. Teammates who are now coaches/directors
        if teammates and teammates.get("all_teammates"):
            for tm in teammates["all_teammates"]:
                if tm.get("is_coach") or tm.get("is_director"):
                    role_type = "Coach" if tm.get("is_coach") else "Director"
                    tm_url = tm.get("trainer_url") or tm.get("url", "")
                    network_contacts.append({
                        "name": tm.get("name", ""),
                        "role": role_type,
                        "current_club": tm.get("current_club", ""),
                        "connection": f"{tm.get('shared_matches', 0)} games",
                        "url": tm_url,
                        "category": "Former Teammates",
                        "category_order": 3,
                        "strength": tm.get("shared_matches", 0),
                    })

        # 2. Companions (Sports Directors, Co-Trainers, Former Bosses)
        # Only add if not already in decision_makers (avoid duplicates)
        companions_data = data.get("companions")
        if companions_data and not decision_makers_data:  # Fallback if decision_makers not available
            # Current SD
            current_sd = companions_data.get("current_sports_director")
            if current_sd:
                network_contacts.append({
                    "name": current_sd.get("name", ""),
                    "role": current_sd.get("role", "Sports Director"),
                    "current_club": current_sd.get("club_name", ""),
                    "connection": "Current",
                    "url": current_sd.get("url", ""),
                    "category": "Sports Directors",
                    "category_order": 1,
                    "strength": 100,
                })

            # All SDs from career
            for sd in companions_data.get("all_sports_directors", []):
                if current_sd and sd.get("name") == current_sd.get("name"):
                    continue
                network_contacts.append({
                    "name": sd.get("name", ""),
                    "role": sd.get("role", "Sports Director"),
                    "current_club": sd.get("club_name", ""),
                    "connection": sd.get("club_name", ""),
                    "url": sd.get("url", ""),
                    "category": "Sports Directors",
                    "category_order": 1,
                    "strength": 50,
                })

        # Former bosses (always show - not duplicated in decision_makers)
        if companions_data:
            for boss in companions_data.get("former_bosses", []):
                network_contacts.append({
                    "name": boss.get("name", ""),
                    "role": "Head Coach",
                    "current_club": boss.get("club_name", ""),
                    "connection": boss.get("club_name", ""),
                    "url": boss.get("url", ""),
                    "category": "Former Bosses",
                    "category_order": 4,
                    "strength": 75,
                })

            # Co-Trainers
            for ct in companions_data.get("current_co_trainers", []):
                network_contacts.append({
                    "name": ct.get("name", ""),
                    "role": ct.get("role", "Assistant Coach"),
                    "current_club": profile.get("current_club", ""),
                    "connection": "Current",
                    "url": ct.get("url", ""),
                    "category": "Assistant Coaches",
                    "category_order": 5,
                    "strength": 90,
                })

            # Management contacts (skip if already in decision_makers to avoid duplicates)
            if not decision_makers_data:
                for mgmt in companions_data.get("all_management", []):
                    network_contacts.append({
                        "name": mgmt.get("name", ""),
                        "role": mgmt.get("role", "Executive"),
                        "current_club": mgmt.get("club_name", ""),
                        "connection": mgmt.get("club_name", ""),
                        "url": mgmt.get("url", ""),
                        "category": "Management",
                        "category_order": 2,
                        "strength": 40,
                    })

        # 3. License cohort mates
        coach_name_for_cohort = profile.get("name", "")
        cohort_num = find_cohort_for_coach(coach_name_for_cohort)
        if cohort_num:
            cohort_mates = get_cohort_mates(coach_name_for_cohort)
            for mate in cohort_mates:
                network_contacts.append({
                    "name": mate.get("name", ""),
                    "role": "Coach",
                    "current_club": mate.get("note", ""),
                    "connection": f"Cohort {cohort_num}",
                    "url": "",
                    "category": "License Cohort",
                    "category_order": 6,
                    "strength": 30,
                })

        # Display summary
        if network_contacts:
            # Sort: category first, then by strength
            network_contacts.sort(key=lambda x: (x.get("category_order", 99), -x.get("strength", 0)))

            st.subheader("Professional Football Network")

            # P2.1: Network Summary Stats
            summary_cols = st.columns(4)
            with summary_cols[0]:
                total_contacts = len(network_contacts)
                st.metric("🌐 Total Contacts", total_contacts)
            with summary_cols[1]:
                coaches_count = sum(1 for c in network_contacts if "Coach" in c.get("role", ""))
                st.metric("🎯 Coaches", coaches_count)
            with summary_cols[2]:
                directors_count = sum(1 for c in network_contacts if "Director" in c.get("role", ""))
                st.metric("📋 Directors", directors_count)
            with summary_cols[3]:
                unique_clubs = len(set(c.get("current_club", "") for c in network_contacts if c.get("current_club")))
                st.metric("🏟️ Clubs", unique_clubs)

            st.divider()

            # Count by category
            categories = {}
            for c in network_contacts:
                cat = c.get("category", "Other")
                categories[cat] = categories.get(cat, 0) + 1

            # Category color mapping
            CATEGORY_COLORS = {
                "🎯 Hiring Managers": "#e63946",  # Red (primary color)
                "Sports Directors": "#9b59b6",  # Purple
                "Executives": "#457b9d",        # Blue
                "Former Teammates": "#3498db",  # Light Blue
                "Former Bosses": "#e74c3c",     # Red-Orange
                "Assistant Coaches": "#2ecc71", # Green
                "Management": "#f39c12",        # Orange
                "License Cohort": "#1abc9c",    # Teal
            }

            # View toggle
            view_mode = st.radio(
                "View",
                ["📊 Table", "🕸️ Network Graph"],
                horizontal=True,
                key="network_view_mode"
            )

            # Get unique values for filters
            all_roles = sorted(set(c.get("role", "") for c in network_contacts if c.get("role")))
            all_categories = sorted(set(c.get("category", "") for c in network_contacts if c.get("category")))
            all_clubs = sorted(set(c.get("current_club", "") for c in network_contacts if c.get("current_club")))

            # Filter row
            filter_cols = st.columns([2, 2, 2, 3])

            with filter_cols[0]:
                selected_categories = st.multiselect(
                    "Type",
                    options=all_categories,
                    default=None,
                    placeholder="All types"
                )

            with filter_cols[1]:
                selected_roles = st.multiselect(
                    "Role",
                    options=all_roles,
                    default=None,
                    placeholder="All roles"
                )

            with filter_cols[2]:
                selected_clubs = st.multiselect(
                    "Club",
                    options=all_clubs,
                    default=None,
                    placeholder="All clubs"
                )

            with filter_cols[3]:
                search_term = st.text_input("🔍 Search name", "", placeholder="Enter name...")

            # Apply filters
            filtered_contacts = network_contacts

            if selected_categories:
                filtered_contacts = [c for c in filtered_contacts if c.get("category") in selected_categories]

            if selected_roles:
                filtered_contacts = [c for c in filtered_contacts if c.get("role") in selected_roles]

            if selected_clubs:
                filtered_contacts = [c for c in filtered_contacts if c.get("current_club") in selected_clubs]

            if search_term:
                filtered_contacts = [c for c in filtered_contacts if search_term.lower() in c.get("name", "").lower()]

            # Stats row with category badges
            badge_html = " ".join([
                f'<span style="background:{CATEGORY_COLORS.get(cat, "#666")};color:white;padding:2px 8px;border-radius:12px;font-size:0.8em;margin-right:4px;">{cat}: {count}</span>'
                for cat, count in categories.items()
            ])
            st.markdown(f"**{len(filtered_contacts)}** of **{len(network_contacts)}** contacts &nbsp;&nbsp; {badge_html}", unsafe_allow_html=True)

            if view_mode == "🕸️ Network Graph":
                # Limit slider for large networks
                max_nodes_default = min(50, len(filtered_contacts))
                if len(filtered_contacts) > 30:
                    graph_limit = st.slider(
                        "Max contacts to display",
                        min_value=10,
                        max_value=min(100, len(filtered_contacts)),
                        value=max_nodes_default,
                        step=10,
                        help="Limit nodes for better performance"
                    )
                    # Sort by strength and take top N
                    display_contacts = sorted(filtered_contacts, key=lambda x: -x.get("strength", 0))[:graph_limit]
                else:
                    display_contacts = filtered_contacts

                # Build graph nodes and edges
                nodes = []
                edges = []

                # Central node (the coach) - with image if available
                coach_name_display = profile.get("name", "Coach")
                coach_image = profile.get("image_url", "")

                if coach_image:
                    nodes.append(Node(
                        id="coach_center",
                        label=coach_name_display,
                        size=50,
                        color="#e74c3c",
                        font={"color": "#ffffff", "size": 14, "strokeWidth": 2, "strokeColor": "#000"},
                        shape="circularImage",
                        image=coach_image,
                        borderWidth=4,
                        borderWidthSelected=6,
                        x=0,
                        y=0,
                        physics=False,  # Fixed center position
                    ))
                else:
                    nodes.append(Node(
                        id="coach_center",
                        label=coach_name_display,
                        size=50,
                        color="#e74c3c",
                        font={"color": "#ffffff", "size": 14, "strokeWidth": 2, "strokeColor": "#000"},
                        shape="dot",
                        borderWidth=4,
                        borderWidthSelected=6,
                        x=0,
                        y=0,
                        physics=False,  # Fixed center position
                    ))

                # Group contacts by category for radial positioning
                import math
                contacts_by_category = {}
                seen_names = set()
                for c in display_contacts:
                    name = c.get("name", "")
                    if not name or name in seen_names:
                        continue
                    seen_names.add(name)
                    category = c.get("category", "Other")
                    if category not in contacts_by_category:
                        contacts_by_category[category] = []
                    contacts_by_category[category].append(c)

                # Calculate radial positions - each category gets a sector
                category_list = list(contacts_by_category.keys())
                num_categories = len(category_list)

                # Quick Win: Radii based on strength - stronger contacts closer to center
                inner_radius = 150   # Closest (strongest connections)
                outer_radius = 350   # Furthest (weakest connections)

                # Quick Win: Gap between categories (in radians)
                category_gap = 0.15  # ~8.5 degrees gap between sectors

                for cat_idx, (category, contacts) in enumerate(contacts_by_category.items()):
                    color = CATEGORY_COLORS.get(category, "#666666")
                    num_in_cat = len(contacts)

                    # Calculate angle range for this category with gaps
                    total_angle = 2 * math.pi
                    usable_angle = total_angle - (num_categories * category_gap)
                    sector_size = usable_angle / num_categories

                    start_angle = cat_idx * (sector_size + category_gap)
                    end_angle = start_angle + sector_size
                    mid_angle = (start_angle + end_angle) / 2

                    # Quick Win: Add category label at the edge of each sector
                    label_radius = outer_radius + 60
                    label_x = label_radius * math.cos(mid_angle)
                    label_y = label_radius * math.sin(mid_angle)

                    nodes.append(Node(
                        id=f"label_{category}",
                        label=category,
                        size=1,  # Tiny node
                        color="#ffffff00",  # Transparent
                        font={"color": color, "size": 14, "bold": True},
                        shape="text",
                        x=label_x,
                        y=label_y,
                        physics=False,
                        fixed=True,
                    ))

                    for idx, c in enumerate(contacts):
                        name = c.get("name", "")
                        strength = c.get("strength", 30)

                        # Position within the category's sector
                        if num_in_cat > 1:
                            angle = start_angle + (idx / (num_in_cat - 1)) * (end_angle - start_angle) * 0.9 + (end_angle - start_angle) * 0.05
                        else:
                            angle = mid_angle

                        # Quick Win: Stronger connections closer to center (inverted radius)
                        # strength 100 -> inner_radius, strength 0 -> outer_radius
                        strength_normalized = min(100, max(0, strength)) / 100
                        node_radius = outer_radius - (strength_normalized * (outer_radius - inner_radius))

                        x = node_radius * math.cos(angle)
                        y = node_radius * math.sin(angle)

                        # Node size based on connection strength
                        node_size = max(15, min(28, 15 + strength / 12))

                        # Shorter label for better readability
                        short_name = name.split()[-1] if len(name) > 15 else name

                        nodes.append(Node(
                            id=name,
                            label=short_name,
                            size=node_size,
                            color=color,
                            font={"color": "#333", "size": 10},
                            title=f"{name}\n{c.get('role', '')} @ {c.get('current_club', '')}\n{c.get('connection', '')}",
                            borderWidth=2,
                            x=x,
                            y=y,
                            physics=False,  # Fixed position
                        ))

                        # Edge from coach to contact
                        edge_width = max(1, min(4, strength / 30))
                        edges.append(Edge(
                            source="coach_center",
                            target=name,
                            color={"color": color, "opacity": 0.5},
                            width=edge_width,
                        ))

                # Graph config - radial layout with fixed positions
                config = Config(
                    width="100%",
                    height=750,  # Increased for category labels
                    directed=False,
                    physics=False,  # Disable physics - use fixed positions
                    hierarchical=False,
                    nodeHighlightBehavior=True,
                    highlightColor="#f1c40f",
                    collapsible=False,
                    node={"labelProperty": "label", "renderLabel": True},
                    link={"labelProperty": "label", "renderLabel": False},
                )

                # Render graph
                if nodes:
                    agraph(nodes=nodes, edges=edges, config=config)
                    if len(filtered_contacts) > len(display_contacts):
                        st.caption(f"Showing top {len(display_contacts)} of {len(filtered_contacts)} contacts (sorted by connection strength)")
                else:
                    st.info("No contacts to display in graph")

                # Compact legend
                legend_cols = st.columns(len([c for c in CATEGORY_COLORS if c in categories]))
                for i, (cat, color) in enumerate([(c, CATEGORY_COLORS[c]) for c in CATEGORY_COLORS if c in categories]):
                    with legend_cols[i]:
                        st.markdown(f'<span style="color:{color}">●</span> {cat}', unsafe_allow_html=True)

            else:
                # Table view
                table_data = []
                for c in filtered_contacts:
                    category = c.get("category", "")
                    color = CATEGORY_COLORS.get(category, "#666")
                    table_data.append({
                        "Name": c.get("name", ""),
                        "Current Role": c.get("role", ""),
                        "Type": category,
                        "Connection": c.get("connection", ""),
                        "Club": c.get("current_club", ""),
                        "Link": c.get("url", ""),
                    })

                st.dataframe(
                    table_data,
                    use_container_width=True,
                    hide_index=True,
                    height=500,
                    column_config={
                        "Name": st.column_config.TextColumn("Name", width="medium"),
                        "Current Role": st.column_config.TextColumn("Current Role", width="small"),
                        "Type": st.column_config.TextColumn("Type", width="small"),
                        "Connection": st.column_config.TextColumn("Connection", width="small"),
                        "Club": st.column_config.TextColumn("Club", width="medium"),
                        "Link": st.column_config.LinkColumn("TM", display_text="🔗", width="small"),
                    }
                )

            # Download button (always visible)
            csv_data = "Name,Role,Type,Connection,Club,URL\n"
            for c in filtered_contacts:
                csv_data += f"\"{c.get('name','')}\",\"{c.get('role','')}\",\"{c.get('category','')}\",\"{c.get('connection','')}\",\"{c.get('current_club','')}\",\"{c.get('url','')}\"\n"

            st.download_button(
                "📥 CSV Export",
                data=csv_data,
                file_name=f"{profile.get('name', 'coach')}_network.csv",
                mime="text/csv"
            )

        else:
            st.info("Load the Companions data in the 'Companions' tab to see the full network")

    # ===== TAB 3: CAREER OVERVIEW =====
    with tab_career:
        st.subheader("📋 Career Overview & Achievements")
        st.caption("Complete career history: playing career, coaching stations, titles won")

        # Get coach name for session state keys
        coach_name = profile.get("name", "unknown")

        # Career Timeline removed - full details shown in Coaching Stations table below

        col_career, col_titles = st.columns(2)

        with col_career:
            st.markdown("#### ⚽ Playing Career")

            # Check if coach had a playing career (from teammates data)
            has_playing_career = teammates and teammates.get("player_id")

            if has_playing_career:
                player_id = teammates.get("player_id")
                total_teammates = teammates.get("total_teammates", 0)

                st.success(f"**Former Professional Player**")

                # Try to get detailed playing career
                career_key = f"playing_career_{coach_name}"
                if career_key not in st.session_state:
                    st.session_state[career_key] = None

                # Check if we already have playing_career from achievements fetch
                titles_key = f"titles_{coach_name}"
                titles_data = st.session_state.get(titles_key)
                if titles_data and titles_data.get("playing_career"):
                    st.session_state[career_key] = titles_data["playing_career"]

                playing_career = st.session_state.get(career_key)

                if playing_career and playing_career.get("stations"):
                    # Show detailed career stations
                    stations = playing_career["stations"]
                    total_apps = playing_career.get("total_appearances", 0)
                    total_goals = playing_career.get("total_goals", 0)

                    st.metric("Total Appearances", total_apps)
                    if total_goals > 0:
                        st.metric("Total Goals", total_goals)

                    st.markdown("**Career Stations:**")
                    for station in stations[:10]:  # Show top 10
                        season = station.get("season", "")
                        club = station.get("club", "")
                        apps = station.get("appearances", 0)
                        goals = station.get("goals", 0)
                        goals_str = f" ({goals} goals)" if goals > 0 else ""
                        st.markdown(f"- **{season}**: {club} - {apps} apps{goals_str}")

                    if len(stations) > 10:
                        st.caption(f"... and {len(stations) - 10} more stations")
                else:
                    # Show summary from teammates data
                    st.metric("Former Teammates", total_teammates)

                    all_tm = teammates.get("all_teammates", [])
                    if all_tm:
                        max_matches = max(tm.get("shared_matches", 0) for tm in all_tm) if all_tm else 0

                        st.markdown("**Key Teammates (Top 5 by shared games):**")
                        for tm in all_tm[:5]:
                            shared = tm.get("shared_matches", 0)
                            name = tm.get("name", "")
                            pos = tm.get("position", "")
                            is_coach = "🎯" if tm.get("is_coach") else ""
                            st.markdown(f"- {name} ({pos}) - {shared} games {is_coach}")

                    st.caption("💡 Click 'Load Titles' to fetch detailed playing career")
            else:
                st.info("No playing career found (coach may have started directly in coaching)")

        with col_titles:
            st.markdown("#### 🏆 Titles & Achievements")

            # Get coach URL and ID for achievements scraping
            coach_url = profile.get("url", "")
            coach_id = profile.get("coach_id")

            # Try to load or fetch titles data
            titles_key = f"titles_{coach_name}"
            if titles_key not in st.session_state:
                st.session_state[titles_key] = None

            # Button to load titles
            if st.session_state[titles_key] is None:
                if st.button("🏆 Load Titles from Transfermarkt", key="load_titles"):
                    if coach_url and coach_id:
                        with st.spinner("Fetching titles..."):
                            achievements = scrape_coach_achievements(coach_url, str(coach_id))
                            st.session_state[titles_key] = achievements
                            st.rerun()
                    else:
                        st.warning("Coach URL/ID not available")

            # Display titles if loaded
            titles_data = st.session_state.get(titles_key)
            if titles_data and titles_data.get("titles"):
                titles = titles_data["titles"]
                total = titles.get("total_titles", 0)

                if titles.get("titles"):
                    st.success(f"**{total} Title{'s' if total != 1 else ''} Found**")
                    for title in titles.get("titles", []):
                        count = title.get("count", 1)
                        name = title.get("name", "")
                        years = title.get("years", "")
                        emoji = "🥇" if "Meister" in name else "🏆" if "Pokal" in name or "Cup" in name else "🎖️"
                        st.markdown(f"{emoji} **{name}** x{count}")
                        if years:
                            st.caption(f"   {years}")
                else:
                    st.info("No titles found on Transfermarkt")

            # Career Statistics (always show if data available)
            if players_used and players_used.get("stations"):
                stations = players_used["stations"]

                st.markdown("---")
                st.markdown("**📊 Coaching Career Statistics:**")

                # Calculate career highlights
                total_wins = sum(s.get("wins", 0) for s in stations)
                total_draws = sum(s.get("draws", 0) for s in stations)
                total_losses = sum(s.get("losses", 0) for s in stations)
                total_games = total_wins + total_draws + total_losses

                # Best PPG station
                best_ppg = 0
                best_ppg_club = ""
                for s in stations:
                    w, d, l = s.get("wins", 0), s.get("draws", 0), s.get("losses", 0)
                    games = w + d + l
                    if games >= 10:  # Minimum 10 games for relevance
                        ppg = (w * 3 + d) / games if games > 0 else 0
                        if ppg > best_ppg:
                            best_ppg = ppg
                            best_ppg_club = s.get("club", "")

                # Win rate
                win_rate = (total_wins / total_games * 100) if total_games > 0 else 0

                stat_cols = st.columns(2)
                with stat_cols[0]:
                    st.metric("Total Wins", total_wins)
                    st.metric("Win Rate", f"{win_rate:.1f}%")
                with stat_cols[1]:
                    st.metric("Best PPG", f"{best_ppg:.2f}")
                    st.caption(f"at {best_ppg_club}" if best_ppg_club else "")

                # Unique clubs coached
                unique_clubs = len(set(s.get("club", "") for s in stations))
                st.metric("Clubs Coached", unique_clubs)

                # Pro License Cohort info
                coach_name_for_cohort = profile.get("name", "")
                cohort_num = find_cohort_for_coach(coach_name_for_cohort)
                if cohort_num:
                    cohort_info = get_cohort_info(cohort_num)
                    st.markdown("---")
                    st.markdown(f"**🎓 Pro License:** {cohort_info.get('name', '')} ({cohort_info.get('year', '')})")

        # Coaching Stations - merged from old tab3
        st.divider()
        st.markdown("### 🏟️ Coaching Stations")
        if players_used and players_used.get("stations"):
            # Reuse stats calculated above (avoid duplication)
            career_ppg = (total_wins * 3 + total_draws) / total_games if total_games > 0 else 0

            # PPG Summary
            ppg_cols = st.columns(4)
            ppg_cols[0].metric("Career PPG", f"{career_ppg:.2f}")
            ppg_cols[1].metric("Wins", total_wins)
            ppg_cols[2].metric("Draws", total_draws)
            ppg_cols[3].metric("Losses", total_losses)

            st.divider()

            # Coaching Stations Table with PPG color indicators
            st.markdown("#### 📊 Coaching Career")

            # PPG Legend
            legend_cols = st.columns(4)
            with legend_cols[0]:
                st.markdown("🟢 PPG ≥2.0 (Excellent)")
            with legend_cols[1]:
                st.markdown("🔵 PPG ≥1.5 (Good)")
            with legend_cols[2]:
                st.markdown("🟠 PPG ≥1.0 (Average)")
            with legend_cols[3]:
                st.markdown("🔴 PPG <1.0 (Below avg)")

            st.markdown("")

            # Build table data with PPG indicator and parsed period
            stations_data = []
            for station in players_used["stations"]:
                wins = station.get("wins", 0)
                draws = station.get("draws", 0)
                losses = station.get("losses", 0)
                games = wins + draws + losses
                ppg = (wins * 3 + draws) / games if games > 0 else 0
                period = station.get("period", "")

                # PPG color indicator
                if ppg >= 2.0:
                    ppg_indicator = "🟢"
                elif ppg >= 1.5:
                    ppg_indicator = "🔵"
                elif ppg >= 1.0:
                    ppg_indicator = "🟠"
                else:
                    ppg_indicator = "🔴"

                # Parse period to shorter format (e.g., "07.2024 - current")
                period_short = period
                if period:
                    # Try to extract dates
                    date_matches = re.findall(r'(\w+)\s+\d+,?\s+(\d{4})', period)
                    if date_matches:
                        month_map = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                                    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                                    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
                        parts = []
                        for month, year in date_matches:
                            m = month_map.get(month[:3], "??")
                            parts.append(f"{m}.{year}")
                        if len(parts) == 2:
                            period_short = f"{parts[0]} - {parts[1]}"
                        elif len(parts) == 1:
                            period_short = f"{parts[0]} - current"

                stations_data.append({
                    "": ppg_indicator,
                    "Club": station.get("club", "Unknown"),
                    "Period": period_short if period_short else "-",
                    "Games": games,
                    "W": wins,
                    "D": draws,
                    "L": losses,
                    "PPG": round(ppg, 2),
                    "Players": station.get("players_used", 0),
                })

            st.dataframe(
                stations_data,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "": st.column_config.TextColumn("", width="small"),
                    "Club": st.column_config.TextColumn("Club", width="medium"),
                    "Period": st.column_config.TextColumn("Period", width="small"),
                    "Games": st.column_config.NumberColumn("G", width="small"),
                    "W": st.column_config.NumberColumn("W", width="small"),
                    "D": st.column_config.NumberColumn("D", width="small"),
                    "L": st.column_config.NumberColumn("L", width="small"),
                    "PPG": st.column_config.NumberColumn("PPG", width="small", format="%.2f"),
                    "Players": st.column_config.NumberColumn("Players", width="small"),
                }
            )
        else:
            st.info("No coaching stations data available")

    # ===== TAB 4: PERFORMANCE =====
    with tab_performance:
        st.subheader("⚽ Performance & Network")
        st.caption("Players coached, teammates from playing career, and coaching companions")

        # Section 1: Players Coached (moved from old tab5)
        st.markdown("### ⚽ Players Coached")

        if players_used and players_used.get("players"):
            players_list = players_used["players"]

            # Filter: Players with 20+ games and 70+ avg minutes
            key_players = [
                p for p in players_list
                if p.get("games", 0) >= 20 and p.get("avg_minutes", 0) >= 70
            ]

            if key_players:
                st.info(f"📊 Showing {len(key_players)} key players (20+ games, 70+ avg minutes)")

                players_data = []
                for p in key_players[:50]:  # Top 50
                    players_data.append({
                        "Player": p.get("name", "Unknown"),
                        "Nationality": p.get("nationality", ""),
                        "Position": p.get("position", ""),
                        "Games": p.get("games", 0),
                        "Goals": p.get("goals", 0),
                        "Assists": p.get("assists", 0),
                        "Avg Min": round(p.get("avg_minutes", 0)),
                        "Profile": p.get("url", ""),
                    })

                st.dataframe(
                    players_data,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Player": st.column_config.TextColumn("Player", width="medium"),
                        "Nationality": st.column_config.TextColumn("Nat", width="small"),
                        "Position": st.column_config.TextColumn("Pos", width="small"),
                        "Games": st.column_config.NumberColumn("G", width="small"),
                        "Goals": st.column_config.NumberColumn("⚽", width="small"),
                        "Assists": st.column_config.NumberColumn("🅰️", width="small"),
                        "Avg Min": st.column_config.NumberColumn("Min/G", width="small"),
                        "Profile": st.column_config.LinkColumn("🔗", width="small", display_text="View"),
                    }
                )
            else:
                st.info("No key players found (filter: 20+ games, 70+ avg minutes)")
        else:
            st.info("No players coached data available")

        st.divider()

        # Section 2: Teammates from Playing Career (moved from old tab4)
        st.markdown("### 👥 Teammates from Playing Career")
        if teammates and teammates.get("all_teammates"):
            tm_list = teammates["all_teammates"]
            total_in_list = len(tm_list)

            # Initialize display limit in session state (use coach-specific key)
            coach_name = profile.get("name", "unknown")
            tm_limit_key = f"teammates_limit_{coach_name}"
            if tm_limit_key not in st.session_state:
                st.session_state[tm_limit_key] = 25

            display_limit = st.session_state[tm_limit_key]

            # Count teammates who are now coaches/directors
            coaches_count = sum(1 for tm in tm_list if tm.get("is_coach"))
            directors_count = sum(1 for tm in tm_list if tm.get("is_director"))

            # Header row with stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Teammates", total_in_list)
            with col2:
                total_matches = sum(tm.get("shared_matches", 0) for tm in tm_list)
                st.metric("Shared Matches", f"{total_matches:,}")
            with col3:
                total_mins = sum(tm.get("total_minutes", 0) for tm in tm_list)
                st.metric("Shared Minutes", f"{total_mins:,}")
            with col4:
                if coaches_count > 0 or directors_count > 0:
                    st.metric("Now Coaches/Directors", f"{coaches_count + directors_count}")
                else:
                    st.metric("Now Coaches/Directors", "?")

            # Action buttons row
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                # Expand button
                if display_limit < total_in_list:
                    remaining = total_in_list - display_limit
                    if st.button(f"➕ Show more ({remaining} remaining)", key="expand_teammates_btn", type="primary"):
                        st.session_state[tm_limit_key] = min(display_limit + 25, total_in_list)
                        st.rerun()
                else:
                    st.success(f"✓ All {total_in_list} teammates shown")
            with btn_col2:
                # Button to enrich with current roles - check ALL teammates
                if coaches_count == 0 and directors_count == 0:
                    if st.button(f"🔍 Load current roles ({total_in_list} teammates)", key="enrich_teammates_roles",
                                 help=f"Checks ALL {total_in_list} teammates if they are now coaches or directors"):
                        progress_bar = st.progress(0, text="Starting analysis...")
                        status_text = st.empty()

                        def update_progress(current, total, name):
                            progress = current / total
                            progress_bar.progress(progress, text=f"Checking {current}/{total}: {name}")

                        enriched = enrich_teammates_with_current_roles(
                            tm_list,
                            max_to_enrich=None,  # ALL teammates!
                            progress_callback=update_progress
                        )

                        # Count results
                        new_coaches = sum(1 for tm in enriched if tm.get("is_coach"))
                        new_directors = sum(1 for tm in enriched if tm.get("is_director"))

                        progress_bar.progress(1.0, text=f"✅ Done! {new_coaches} coaches, {new_directors} directors found")
                        st.session_state.coach_data["teammates"]["all_teammates"] = enriched
                        st.rerun()

            st.divider()

            # Show as table with limit - include current role if available
            table_data = []
            for tm in tm_list[:display_limit]:
                row = {
                    "Name": tm.get("name", ""),
                    "Position": tm.get("position", ""),
                    "Shared Matches": tm.get("shared_matches", 0),
                    "Teams Together": tm.get("teams_together", 0),
                    "Total Minutes": tm.get("total_minutes", 0),
                }

                # Add current role indicator
                if tm.get("is_coach"):
                    row["Now"] = f"🎯 Coach ({tm.get('current_club', '?')})"
                elif tm.get("is_director"):
                    row["Now"] = f"📋 Director"
                else:
                    row["Now"] = ""

                row["TM Profile"] = tm.get("url", "")
                table_data.append(row)

            st.dataframe(
                table_data,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Name": st.column_config.TextColumn(width="medium"),
                    "Position": st.column_config.TextColumn(width="small"),
                    "Shared Matches": st.column_config.NumberColumn(width="small"),
                    "Teams Together": st.column_config.NumberColumn(width="small"),
                    "Total Minutes": st.column_config.NumberColumn(width="small", format="%d"),
                    "Now": st.column_config.TextColumn(width="medium"),
                    "TM Profile": st.column_config.LinkColumn(
                        "TM Profile",
                        display_text="🔗 Link",
                        width="small"
                    )
                }
            )

            # Footer with count and download
            col_info, col_download = st.columns([3, 1])

            with col_info:
                st.caption(f"Showing {min(st.session_state[tm_limit_key], total_in_list)} of {total_in_list} teammates")

            with col_download:
                # Download button (all data)
                all_table_data = []
                for tm in tm_list:
                    all_table_data.append({
                        "Name": tm.get("name", ""),
                        "Position": tm.get("position", ""),
                        "Shared Matches": tm.get("shared_matches", 0),
                        "Teams Together": tm.get("teams_together", 0),
                        "Total Minutes": tm.get("total_minutes", 0),
                        "TM URL": tm.get("url", "")
                    })
                st.download_button(
                    "📥 CSV (all)",
                    data="\n".join([
                        ",".join(all_table_data[0].keys()),
                        *[",".join(str(v) for v in row.values()) for row in all_table_data]
                    ]),
                    file_name=f"{profile.get('name', 'coach')}_teammates.csv",
                    mime="text/csv"
                )
        else:
            st.info("No teammate data available (coach may not have had a professional playing career)")

        # Section removed - Players Coached now at top of Performance tab

        # OLD TAB5 CODE BELOW - TO BE REMOVED OR INTEGRATED
        players_detail = data.get("players_detail", {})

        if players_detail and players_detail.get("players"):
            player_list = players_detail["players"]

            # Use coach-specific key for display limit
            players_limit_key = f"players_limit_{coach_name}"
            if players_limit_key not in st.session_state:
                st.session_state[players_limit_key] = 25

            display_limit = st.session_state[players_limit_key]
            total_players_available = players_detail.get("total_players", len(player_list))

            # Summary stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Players Loaded", len(player_list))
            with col2:
                total_mins = sum(p.get("minutes", 0) for p in player_list)
                st.metric("Total Minutes", f"{total_mins:,}")
            with col3:
                total_apps = sum(p.get("appearances", 0) for p in player_list)
                st.metric("Total Appearances", total_apps)

            # Action buttons in separate row
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                # Button to load agent info
                if st.button("🔄 Load Agent Info", help="Fetches agent and contract data for all players (~30 sec)"):
                    with st.spinner(f"Fetching agent info for {len(player_list)} players..."):
                        enriched = enrich_players_with_agents(player_list, max_players=len(player_list))
                        st.session_state.coach_data["players_detail"]["players"] = enriched
                        st.rerun()
            with btn_col2:
                # Expand display (show more from already loaded data)
                if display_limit < len(player_list):
                    remaining = len(player_list) - display_limit
                    if st.button(f"➕ Show more ({remaining} remaining)", key="expand_players_display", type="primary"):
                        st.session_state[players_limit_key] = min(display_limit + 25, len(player_list))
                        st.rerun()
                else:
                    st.success(f"✓ All {len(player_list)} shown")
            with btn_col3:
                # Download all players CSV
                pass  # Placeholder, download is at bottom

            st.divider()

            # Check if agent info is loaded
            has_agent_info = any(p.get("agent") for p in player_list)

            # Player table with display limit
            current_display = st.session_state[players_limit_key]
            table_data = []
            for i, player in enumerate(player_list[:current_display], 1):
                row_data = {
                    "#": i,
                    "Player": player.get("name", ""),
                    "Position": player.get("position", ""),
                    "Age": player.get("age", ""),
                    "Appearances": player.get("appearances", 0),
                    "Minutes": player.get("minutes", 0),
                    "Goals": player.get("goals", 0),
                    "Assists": player.get("assists", 0),
                    "Market Value": player.get("market_value", "-"),
                    "TM Profile": player.get("url", ""),
                }

                if has_agent_info:
                    row_data["Agent"] = player.get("agent", "-")
                    row_data["Contract Until"] = player.get("contract_until", "-")

                table_data.append(row_data)

            # Build column config
            column_config = {
                "#": st.column_config.NumberColumn(width=40),
                "Player": st.column_config.TextColumn(width="medium"),
                "Position": st.column_config.TextColumn(width=140),
                "Age": st.column_config.NumberColumn(width=50),
                "Appearances": st.column_config.NumberColumn(width=70),
                "Minutes": st.column_config.NumberColumn(width=70, format="%d"),
                "Goals": st.column_config.NumberColumn(width=55),
                "Assists": st.column_config.NumberColumn(width=55),
                "Market Value": st.column_config.TextColumn(width=90),
                "TM Profile": st.column_config.LinkColumn(
                    "TM Profile",
                    display_text="🔗 Link",
                    width=70
                ),
            }

            if has_agent_info:
                column_config["Agent"] = st.column_config.TextColumn(width="medium")
                column_config["Contract Until"] = st.column_config.TextColumn(width="small")

            st.dataframe(
                table_data,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )

            # Footer: count and download
            col_info, col_download = st.columns([3, 1])

            with col_info:
                shown = min(st.session_state[players_limit_key], len(player_list))
                st.caption(f"Showing {shown} of {len(player_list)} loaded players (from {total_players_available} total)")

            with col_download:
                # Download CSV (all loaded data) - include TM URL
                if has_agent_info:
                    csv_header = "Rank,Player,Position,Age,Appearances,Minutes,Goals,Assists,Market Value,Agent,Contract Until,TM URL\n"
                    csv_rows = [f"{i},{p.get('name','')},{p.get('position','')},{p.get('age','')},{p.get('appearances',0)},{p.get('minutes',0)},{p.get('goals',0)},{p.get('assists',0)},{p.get('market_value','-')},{p.get('agent','-')},{p.get('contract_until','-')},{p.get('url','')}" for i, p in enumerate(player_list, 1)]
                else:
                    csv_header = "Rank,Player,Position,Age,Appearances,Minutes,Goals,Assists,Market Value,TM URL\n"
                    csv_rows = [f"{i},{p.get('name','')},{p.get('position','')},{p.get('age','')},{p.get('appearances',0)},{p.get('minutes',0)},{p.get('goals',0)},{p.get('assists',0)},{p.get('market_value','-')},{p.get('url','')}" for i, p in enumerate(player_list, 1)]

                st.download_button(
                    "📥 CSV",
                    data=csv_header + "\n".join(csv_rows),
                    file_name=f"{profile.get('name', 'coach')}_players.csv",
                    mime="text/csv"
                )
        else:
            st.info("No detailed player data available")

        # Companions section - merged into Performance tab
        st.divider()
        st.markdown("### 🤝 Coaching Companions")
        st.caption("Assistant coaches, co-trainers, and former bosses")

        # Button to load companions data
        companions_data = data.get("companions")

        if not companions_data:
            if st.button("🔄 Load Companions", help="Loads data about Sports Directors and Assistant Coaches (~30 sec)"):
                with st.spinner("Loading companions data..."):
                    # Build stations list from players_used data
                    stations_for_companions = []
                    if players_used and players_used.get("stations"):
                        for station in players_used["stations"]:
                            # Extract club_id from URL if available
                            club_url = station.get("club_url", "")
                            club_id = None
                            club_slug = ""

                            import re
                            id_match = re.search(r"/verein/(\d+)", club_url)
                            if id_match:
                                club_id = int(id_match.group(1))

                            slug_match = re.search(r"transfermarkt\.de/([^/]+)/", club_url)
                            if slug_match:
                                club_slug = slug_match.group(1)

                            if club_id:
                                stations_for_companions.append({
                                    "club_id": club_id,
                                    "club_slug": club_slug,
                                    "club_name": station.get("club", "Unknown"),
                                    "start_date": station.get("start_date"),
                                    "end_date": station.get("end_date"),
                                    "club_url": club_url,
                                })

                    if stations_for_companions:
                        coach_id = profile.get("coach_id")
                        coach_url = profile.get("url", "")

                        if coach_id:
                            companions = get_companions_for_coach(coach_id, coach_url, stations_for_companions)
                            st.session_state.coach_data["companions"] = companions
                            st.rerun()
                        else:
                            st.warning("Coach ID not found")
                    else:
                        st.warning("No coaching stations found for comparison")
        else:
            # Display companions data - new structure

            # Section 1: Former Bosses (people this coach worked under as assistant)
            st.markdown("#### 🎯 Former Bosses (worked under as assistant)")
            former_bosses = companions_data.get("former_bosses", [])
            if former_bosses:
                boss_data = []
                for boss in former_bosses:
                    games_str = f"{boss.get('games_together', '-')} games" if boss.get('games_together') else "-"
                    boss_data.append({
                        "Boss": boss.get("name", "Unknown"),
                        "Club": boss.get("club_name", ""),
                        "Period": boss.get("period", ""),
                        "Games Together": games_str,
                    })
                st.dataframe(boss_data, use_container_width=True, hide_index=True)
            else:
                st.info("No former bosses found (was never assistant)")

            st.markdown("---")

            # Section 2: Sports Directors - Current and All
            st.markdown("#### 📋 Sports Directors")
            st.caption("Key decision makers this coach has worked with")

            col_current_sd, col_all_sd = st.columns(2)

            with col_current_sd:
                st.markdown("**🔵 Current Sports Director**")
                current_sd = companions_data.get("current_sports_director")
                if current_sd:
                    sd_url = current_sd.get('url', '')
                    sd_name = current_sd.get('name', 'Unknown')
                    name_display = f"<a href='{sd_url}' target='_blank' style='color: #58a6ff; text-decoration: none;'>{sd_name}</a>" if sd_url else sd_name
                    sd_start = current_sd.get('sd_start', '')
                    since_text = f" (since {sd_start})" if sd_start else ""

                    # Check if they worked together before at other clubs
                    all_directors = companions_data.get("all_sports_directors", [])
                    prev_clubs = [sd.get('club_name') for sd in all_directors if sd.get('name') == current_sd.get('name') and sd.get('club_name') != current_sd.get('club_name')]
                    history_badge = f"<br><span style='color: #ffd700; font-size: 0.9em;'>⭐ Also worked together at: {', '.join(prev_clubs)}</span>" if prev_clubs else ""

                    st.markdown(f"""
                    <div style="background: #1e3a5f; padding: 14px; border-radius: 8px; border-left: 4px solid #58a6ff;">
                        <strong style="color: #fff; font-size: 1.1em;">{name_display}</strong><br>
                        <span style="color: #b8c5d6;">{current_sd.get('role', '')}{since_text}</span><br>
                        <span style="color: #8b9eb3;">📍 {current_sd.get('club_name', '')}</span>{history_badge}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("Not found for current club")

            with col_all_sd:
                st.markdown("**📜 Career History**")
                all_directors = companions_data.get("all_sports_directors", [])
                if all_directors:
                    # Group by person to find repeat relationships
                    sd_by_name = {}
                    for sd in all_directors:
                        name = sd.get("name", "Unknown")
                        if name not in sd_by_name:
                            sd_by_name[name] = []
                        sd_by_name[name].append(sd)

                    for sd_name, clubs_list in sd_by_name.items():
                        # Skip if same as current (already shown prominently)
                        current_name = current_sd.get("name") if current_sd else None
                        if sd_name == current_name:
                            continue

                        sd = clubs_list[0]  # Use first for URL
                        sd_url = sd.get('url', '')
                        name_display = f"<a href='{sd_url}' target='_blank' style='color: #79c0ff; text-decoration: none;'>{sd_name}</a>" if sd_url else sd_name

                        # Show all clubs worked together
                        club_list = [c.get('club_name', '') for c in clubs_list]
                        repeat_badge = "🔄 " if len(club_list) > 1 else ""

                        st.markdown(f"""
                        <div style="background: #2a3f5f; padding: 12px; border-radius: 6px; margin-bottom: 8px; border-left: 3px solid #79c0ff;">
                            <strong style="color: #e6edf3; font-size: 1.05em;">{repeat_badge}{name_display}</strong><br>
                            <span style="color: #8b9eb3;">📍 {', '.join(club_list)}</span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("None found in career")

            st.markdown("---")

            # Section 3: All Management Contacts from Career
            st.markdown("#### 🏢 Club Leadership & Board")
            st.caption("CEOs, Board Members, and Directors who overlapped with coach's tenure")

            all_management = companions_data.get("all_management", [])
            if all_management:
                # Group by club, then by role type
                clubs = {}
                for mgmt in all_management:
                    club = mgmt.get("club_name", "Unknown")
                    if club not in clubs:
                        clubs[club] = {"CEO": [], "Board": [], "Other": []}

                    role = mgmt.get("role", "")
                    if "CEO" in role or "Geschäftsführer" in role or "Vorsitzend" in role:
                        clubs[club]["CEO"].append(mgmt)
                    elif "Vorstand" in role or "Präsident" in role or "Aufsichtsrat" in role:
                        clubs[club]["Board"].append(mgmt)
                    else:
                        clubs[club]["Other"].append(mgmt)

                for club_name, role_groups in clubs.items():
                    with st.expander(f"**{club_name}** ({sum(len(g) for g in role_groups.values())} contacts)", expanded=False):
                        for role_type, managers in role_groups.items():
                            if not managers:
                                continue

                            role_emoji = "👔" if role_type == "CEO" else "🏛️" if role_type == "Board" else "📋"
                            st.markdown(f"**{role_emoji} {role_type}**")

                            mgmt_cols = st.columns(min(len(managers), 2))
                            for i, mgmt in enumerate(managers):
                                with mgmt_cols[i % 2]:
                                    mgmt_url = mgmt.get('url', '')
                                    mgmt_name = mgmt.get('name', 'Unknown')
                                    name_display = f"<a href='{mgmt_url}' target='_blank' style='color: #d2a8ff; text-decoration: none;'>{mgmt_name}</a>" if mgmt_url else mgmt_name
                                    start_date = mgmt.get('start_date', '')
                                    overlap_months = mgmt.get('overlap_months', '')
                                    overlap_text = f"<br><span style='color: #9b9bae; font-size: 0.8em;'>Overlap: ~{overlap_months} months</span>" if overlap_months else ""
                                    st.markdown(f"""
                                    <div style="background: #2d2a3d; padding: 12px; border-radius: 6px; margin-bottom: 8px; border-left: 3px solid #d2a8ff;">
                                        <strong style="color: #e6edf3; font-size: 1em;">{name_display}</strong><br>
                                        <span style="color: #b8a8c9; font-size: 0.9em;">{mgmt.get('role', '')}</span><br>
                                        <span style="color: #8b8b9e; font-size: 0.85em;">since {start_date}</span>{overlap_text}
                                    </div>
                                    """, unsafe_allow_html=True)

                # Summary stats
                total_unique = len(set(m.get('name', '') for m in all_management))
                st.caption(f"📊 Total: {total_unique} unique management contacts across career")
            else:
                st.info("No management contacts with overlapping tenure found")

            st.markdown("---")

            # Section 4: Current Co-Trainers (Enhanced)
            st.markdown("#### 👥 Current Coaching Staff")
            st.caption("Assistant coaches, goalkeeping coaches, and other staff at current club")

            co_trainers = companions_data.get("current_co_trainers", [])
            if co_trainers:
                # Group by role type
                role_groups = {}
                for ct in co_trainers:
                    role = ct.get('role', 'Assistant')
                    # Categorize roles
                    if 'Torwart' in role or 'Goalkeeper' in role:
                        category = "🧤 Goalkeeping"
                    elif 'Athletik' in role or 'Fitness' in role or 'Kondition' in role:
                        category = "💪 Athletic/Fitness"
                    elif 'Co-Trainer' in role or 'Assistent' in role or 'Assistant' in role:
                        category = "📋 Assistant Coaches"
                    elif 'Analyse' in role or 'Video' in role:
                        category = "📊 Analysis"
                    else:
                        category = "👔 Other Staff"

                    if category not in role_groups:
                        role_groups[category] = []
                    role_groups[category].append(ct)

                # Display by category
                for category, staff_list in sorted(role_groups.items()):
                    st.markdown(f"**{category}** ({len(staff_list)})")
                    ct_cols = st.columns(min(len(staff_list), 3))
                    for i, ct in enumerate(staff_list):
                        with ct_cols[i % 3]:
                            ct_url = ct.get('url', '')
                            ct_name = ct.get('name', 'Unknown')
                            name_display = f"<a href='{ct_url}' target='_blank' style='color: #7ee787; text-decoration: none;'>{ct_name}</a>" if ct_url else ct_name
                            role_detail = ct.get('role', '')
                            st.markdown(f"""
                            <div style="background: #1c3d2e; padding: 14px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #7ee787;">
                                <strong style="color: #e6edf3; font-size: 1.05em;">{name_display}</strong><br>
                                <span style="color: #a8c9b8;">{role_detail}</span>
                            </div>
                            """, unsafe_allow_html=True)
            else:
                st.info("No current coaching staff found")

            st.markdown("---")

            # Section 5: License Cohort
            st.markdown("#### 🎓 Pro License Cohort (Fellow Graduates)")

            coach_name = profile.get("name", "")
            cohort_num = find_cohort_for_coach(coach_name)

            if cohort_num:
                cohort_info = get_cohort_info(cohort_num)
                cohort_mates = get_cohort_mates(coach_name)

                st.markdown(f"""
                <div style="background: #3d2e1c; padding: 14px; border-radius: 8px; margin-bottom: 16px; border-left: 4px solid #f0b429;">
                    <strong style="color: #f0b429; font-size: 1.1em;">🏆 {cohort_info.get('name', '')}</strong><br>
                    <span style="color: #d4c5a9;">📅 {cohort_info.get('year', '')}</span><br>
                    <span style="color: #b8a882;">📍 {cohort_info.get('location', '')}</span>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"**{len(cohort_mates)} Fellow Graduates:**")

                # Display in grid
                mate_cols = st.columns(4)
                for i, mate in enumerate(cohort_mates):
                    with mate_cols[i % 4]:
                        note = f"<br><span style='color: #a89060; font-size: 0.85em;'>{mate['note']}</span>" if mate.get('note') else ""
                        st.markdown(f"""
                        <div style="background: #2d2a1c; padding: 10px; border-radius: 6px; margin-bottom: 6px; border-left: 3px solid #c9a227;">
                            <strong style="color: #e6dfc9; font-size: 0.95em;">{mate['name']}</strong>{note}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No cohort data found (not in database or foreign license)")

else:
    # Welcome screen
    st.markdown("""
    ### 👋 Welcome!

    Use the sidebar to search for a coach:

    1. **Direct Search**: Enter a coach name to find them directly
    2. **Browse by League**: Select Bundesliga → Club → View current coach
    """)

    # Quick access buttons
    st.subheader("🚀 Quick Access")

    quick_cols = st.columns(4)

    quick_coaches = [
        ("Alexander Blessin", "FC St. Pauli"),
        ("Kasper Hjulmand", "Bayer Leverkusen"),
        ("Vincent Kompany", "Bayern München"),
        ("Ole Werner", "RB Leipzig")
    ]

    for i, (coach, club) in enumerate(quick_coaches):
        with quick_cols[i]:
            if st.button(f"⚽ {coach}\n{club}", use_container_width=True):
                st.session_state.loading = True
                st.session_state.search_name = coach
                st.rerun()

    # Show league overview if available
    if st.session_state.bundesliga_coaches:
        st.divider()
        st.subheader("📊 Bundesliga Coaches Overview")

        coaches_data = st.session_state.bundesliga_coaches.get("clubs", {})
        if coaches_data:
            # Display as grid with logos (3 columns)
            sorted_clubs = sorted(coaches_data.items())
            cols_per_row = 3

            for i in range(0, len(sorted_clubs), cols_per_row):
                cols = st.columns(cols_per_row)

                for j, (club, info) in enumerate(sorted_clubs[i:i+cols_per_row]):
                    with cols[j]:
                        # Get club logo
                        logo_url = get_club_logo(club)

                        # Display club card
                        if logo_url:
                            st.image(logo_url, width=60)

                        st.markdown(f"**{club}**")
                        coach_name = info.get("coach_name", "Unknown")
                        coach_url = info.get("coach_url", "")

                        if coach_url:
                            st.caption(f"👤 {coach_name}")
                        else:
                            st.caption(f"👤 {coach_name}")

                        st.markdown("")  # Spacing


if __name__ == "__main__":
    pass
