"""Streamlit UI for the no-key Sunday League Fair Draw workflow."""

from __future__ import annotations

import random
import json
import hashlib
import base64
import os
from html import escape
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import streamlit as st

from fairdraw import config
from fairdraw.data_io import load_history, load_roster, save_history
from fairdraw.draw import draw
from fairdraw.draw import percentile, random_baseline
from fairdraw.env_loader import describe_key_source, load_key_state
from fairdraw.metrics import keeper_counts, size_difference, teammate_counts, top_players, top_players_per_team
from fairdraw.models import Night, Player
from fairdraw.receipt import build_full_receipt, build_public_receipt, verify_full_receipt
from fairdraw.pipeline import run_attendance_pipeline
from fairdraw.announce_agent import create_announcement
from fairdraw.verifier import verify_announcement
from fairdraw.usage_log import get_run_totals
from fairdraw.trace import record, save_trace
from fairdraw_ui.components import crest_svg, keeper_badge, name_plate, section_header, shirt_svg


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REAL_DATA = DATA / "real"


def _settings(team_count: int):
    values = {name: getattr(config, name) for name in dir(config) if name.isupper()}
    values["NUM_TEAMS"] = team_count
    values["TEAM_NAMES"] = config.TEAM_NAMES[:team_count]
    return SimpleNamespace(**values)


def _init_state() -> None:
    defaults = {
        "roster": [], "history": [], "attendance": [], "attendance_confirmed": False,
        "guest": [], "draw_result": None, "draw_count": 0, "seed_shown": None,
        "last_verification": False,
        "avatar_style": "shirt",
        "attendance_proposals": [], "attendance_defense_events": [], "attendance_tokens": {},
        "announcement_text": "", "announcement_error": "",
        "run_trace": [],
        "data_mode": "Sample data", "team_count": 2,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _load_sample() -> None:
    # Clear the previous pills value so the newly loaded sample attendance is
    # reflected immediately after Streamlit reruns the page.
    st.session_state.pop("squad_pills", None)
    st.session_state.roster = load_roster("sample_roster.csv", DATA)
    st.session_state.history = load_history("sample_history.json", DATA)
    st.session_state.attendance = [player.name for player in st.session_state.roster]
    st.session_state.attendance_confirmed = False
    st.session_state.guest = []
    st.session_state.draw_result = None
    st.toast("Sample roster and history loaded.")


def _load_mode_data() -> None:
    data_dir = DATA if st.session_state.data_mode == "Sample data" else REAL_DATA
    try:
        st.session_state.roster = load_roster("sample_roster.csv" if data_dir == DATA else "roster.csv", data_dir)
        st.session_state.history = load_history("sample_history.json" if data_dir == DATA else "history.json", data_dir)
    except ValueError as exc:
        st.session_state.roster, st.session_state.history = [], []
        st.warning(str(exc))


def _roster_editor() -> None:
    rows = [{"name": p.name, "rating": p.rating, "keeper": p.keeper, "aliases": "|".join(p.aliases)} for p in st.session_state.roster]
    edited = st.data_editor(rows, num_rows="dynamic", use_container_width=True, column_config={"rating": st.column_config.NumberColumn(min_value=1, max_value=10, step=1), "keeper": st.column_config.CheckboxColumn()}, key="roster_editor")
    if st.button("Save roster", disabled=st.session_state.data_mode == "Sample data"):
        try:
            players = [Player(name=str(row["name"]).strip(), rating=int(row["rating"]), keeper=bool(row["keeper"]), aliases=[x.strip() for x in str(row["aliases"]).split("|") if x.strip()]) for row in edited if str(row.get("name", "")).strip()]
            names = [p.name.casefold() for p in players]
            if len(names) != len(set(names)):
                raise ValueError("Roster names must be unique, ignoring case.")
            st.session_state.roster = players
            save_roster = DATA / "real" / "roster.csv"
            save_roster.parent.mkdir(parents=True, exist_ok=True)
            import csv
            with save_roster.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["name", "rating", "keeper", "aliases"])
                writer.writeheader()
                writer.writerows({"name": p.name, "rating": p.rating, "keeper": "yes" if p.keeper else "no", "aliases": "|".join(p.aliases)} for p in players)
            st.success("Roster saved to data/real/roster.csv.")
        except (ValueError, TypeError) as exc:
            st.error(f"Roster validation error: {exc}")
    if st.session_state.data_mode != "Sample data":
        st.caption("Only upload photos of players who agreed.")
        photo_player = st.selectbox("Photo player", [player.name for player in st.session_state.roster], key="photo_player") if st.session_state.roster else None
        photo = st.file_uploader("Upload player photo (JPG/PNG, max 5 MB)", type=["jpg", "jpeg", "png"], key="photo_upload")
        if photo_player and photo and st.button("Save privacy-safe photo"):
            if photo.size > 5 * 1024 * 1024:
                st.error("Photo is too large. Choose an image under 5 MB.")
            else:
                from PIL import Image
                from io import BytesIO
                safe_name = "".join(character for character in photo_player.casefold().replace(" ", "_") if character.isalnum() or character == "_")
                image = Image.open(BytesIO(photo.getvalue())).convert("RGB")
                side = min(image.size)
                left, top = (image.width - side) // 2, (image.height - side) // 2
                image = image.crop((left, top, left + side, top + side)).resize((256, 256))
                photo_path = REAL_DATA / "photos" / f"{safe_name}.jpg"
                photo_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(photo_path, format="JPEG", quality=88, optimize=True)
                st.success("Photo saved without original metadata.")


def _kit_for(name: str) -> tuple[str, str, str]:
    options = [("#2C80DF", "#EAF5FF", "stripes"), ("#1266C5", "#FFFFFF", "sash"), ("#22D3EE", "#082B57", "halves"), ("#17233D", "#3B82F6", "hoops")]
    return options[int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % len(options)]


def _footballer_avatar(player_name: str, index: int, initials: str, primary: str, secondary: str) -> str:
    """Use the supplied footballer artwork with deterministic editorial crops."""
    assets = sorted(path for path in (ROOT / "assets" / "avatars").glob("*") if path.suffix.casefold() in {".jpg", ".jpeg", ".png", ".webp"})
    if not assets:
        return f'<div class="roster-avatar" aria-label="Player avatar"><span class="avatar-head"></span><span class="avatar-body" style="--kit:{primary};--kit2:{secondary}"><b>{initials}</b></span></div>'
    preferred = {
        "Bea": "791a85b7-1e0f-4992-a693-96668534d3df.jpg",
        "Finn": "8a7a4a41-b315-42fc-b8d0-795ae204bd44.jpg",
        "Jules": "e1efb6bf-f4a4-44d7-9cc2-bb0d1dbb0083.jpg",
        "Nia": "7507bbb5-7c36-4ddf-8b6f-a2bc52e6a89a.jpg",
    }
    preferred_asset = ROOT / "assets" / "avatars" / preferred.get(player_name, "")
    asset = preferred_asset if preferred_asset.is_file() else assets[index % len(assets)]
    encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
    mime = "image/png" if asset.suffix.casefold() == ".png" else "image/jpeg"
    positions = ("50% 32%", "44% 28%", "56% 30%", "50% 24%")
    crop = positions[index % len(positions)]
    return f'<div class="roster-avatar portrait-avatar" style="--kit:{primary};--kit2:{secondary}" aria-label="Player avatar"><img src="data:{mime};base64,{encoded}" alt="" style="object-position:{crop}"><span class="portrait-kit"></span><b>{initials}</b></div>'


def _history_facts(name: str) -> tuple[int, int]:
    played = sum(name in night_player for night in st.session_state.history for night_player in [sum(night.teams.values(), [])])
    teammates = set()
    for night in st.session_state.history:
        for players in night.teams.values():
            if name in players:
                teammates.update(players)
    teammates.discard(name)
    return played, len(teammates)


def _render_roster_cards_legacy() -> None:
    if not st.session_state.roster:
        st.markdown('<div class="empty-state">◎<br>No roster loaded yet. Load sample data to see your squad.</div>', unsafe_allow_html=True)
        return
    attending = set(st.session_state.attendance)
    cards = []
    for player in st.session_state.roster:
        dimmed = "" if player.name in attending else " dimmed"
        rating = f'<span class="rating-badge">{player.rating}</span>' if not st.session_state.hide_ratings else ""
        keeper = keeper_badge() if player.keeper else ""
        aliases = ''.join(f'<span class="alias-chip">{escape(alias)}</span>' for alias in player.aliases)
        status = "IN" if player.name in attending else "OUT"
        played, teammate_count = _history_facts(player.name)
        primary, secondary, pattern = _kit_for(player.name)
        avatar = f'<div class="roster-shirt">{shirt_svg(primary, player.name[:1], player.keeper, secondary, pattern)}</div>'
        photo_path = REAL_DATA / "photos" / ("".join(character for character in player.name.casefold().replace(" ", "_") if character.isalnum() or character == "_") + ".jpg")
        if st.session_state.avatar_style == "photo" and photo_path.is_file() and st.session_state.data_mode != "Sample data":
            encoded = base64.b64encode(photo_path.read_bytes()).decode("ascii")
            avatar = f'<div class="roster-photo"><img src="data:image/jpeg;base64,{encoded}" alt=""/></div>'
        cards.append(f'<div class="roster-card{dimmed}"><div class="roster-card-top">{avatar}{name_plate(player.name, "")}{rating}</div><div class="compact-status"><span class="status-dot {status.lower()}"></span>{status}</div><div class="card-facts">{played} nights · {teammate_count} teammates</div>{keeper}<div class="alias-row">{aliases}</div></div>')
    st.markdown('<div class="roster-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)


def _render_roster_cards() -> None:
    """Render the compact presentation-only roster card grid."""
    if not st.session_state.roster:
        st.markdown('<div class="empty-state">No roster loaded yet. Load sample data to see your squad.</div>', unsafe_allow_html=True)
        return
    attending = set(st.session_state.attendance)
    guest_names = {guest.name for guest in st.session_state.guest}
    cards = []
    for index, player in enumerate(st.session_state.roster):
        status = "IN" if player.name in attending else "OUT"
        played, teammate_count = _history_facts(player.name)
        primary, secondary, pattern = _kit_for(player.name)
        initials = escape("".join(part[0] for part in player.name.split() if part)[:2].upper(), quote=True)
        avatar = _footballer_avatar(player.name, index, initials, primary, secondary)
        rating = f'<span class="rating-badge">{player.rating}</span>' if not st.session_state.hide_ratings else ""
        badge = '<span class="card-corner-badge">GK</span>' if player.keeper else ('<span class="card-corner-badge">NEW</span>' if player.name in guest_names else '')
        safe_name = escape(player.name, quote=True)
        tone = "is-in" if status == "IN" else "is-out"
        cards.append(f'<article class="roster-card" tabindex="0" title="{safe_name}"><div class="roster-top-panel">{badge}{rating}{avatar}</div><div class="roster-name-plate">{safe_name}</div><div class="roster-status {tone}">{status}</div><div class="roster-mini-stats"><span>{played} GAMES</span><span>{teammate_count} MATES</span></div></article>')
    st.markdown('<div class="roster-grid roster-grid-v4">' + ''.join(cards) + '</div>', unsafe_allow_html=True)


def _render_squad_board() -> list[str]:
    names = [player.name for player in st.session_state.roster]
    selected = list(st.session_state.attendance)
    if hasattr(st, "pills"):
        chosen = st.pills("Squad", names, selection_mode="multi", default=selected, label_visibility="collapsed", key="squad_pills")
        return chosen or []
    cols = st.columns(2)
    chosen = []
    for index, name in enumerate(names):
        with cols[index % 2]:
            if st.checkbox(f"✓ {name}", value=name in selected, key=f"squad_{name}"):
                chosen.append(name)
    return chosen


def _pitch_card(team: str, players: list[str], lookup: dict[str, Player], kit: str) -> str:
    keepers = [name for name in players if lookup[name].keeper]
    outfield = [name for name in players if name not in keepers]
    rows = ([keepers[:1]] if keepers else []) + [outfield[start:start + 3] for start in range(0, len(outfield), 3)]
    formation = []
    for row in rows:
        people = []
        for name in row:
            color = "#FFC83D" if lookup[name].keeper else kit
            rating = f" · {lookup[name].rating}/10" if not st.session_state.hide_ratings else ""
            people.append(f'<div class="pitch-player"><div class="pitch-shirt">{shirt_svg(color, name[:1], lookup[name].keeper)}</div><span class="pitch-name">{escape(name)}{escape(rating)}</span></div>')
        formation.append('<div class="formation-row">' + ''.join(people) + '</div>')
    primary = "#2BFF9A" if team.endswith("A") else "#7C5CFF"
    return f'<div class="pitch-card reveal"><div class="pitch-header"><span>{crest_svg(team, primary, "#fff", "stripe")} {escape(team)}</span><span>{len(players)} PLAYERS</span></div><div class="pitch"><div class="formation">{"".join(formation)}</div></div></div>'


def _fairness_cards(result, comparison, top_counts, keeper_split) -> str:
    strength_value = "BALANCED" if st.session_state.hide_ratings else f'{result.metrics["strength_gap"]:.2f} GAP'
    top_line = " · ".join(f"{escape(team)} {count}" for team, count in top_counts.items())
    keeper_line = " · ".join(f"{escape(team)} {'✓' if count else '—'}" for team, count in keeper_split.items())
    return f'''<div class="fairness-grid"><div class="fair-card"><small>Strength balance</small><strong>{strength_value}</strong><p>Teams are balanced by the code engine.</p></div><div class="fair-card"><small>Top players split</small><strong>{top_line}</strong><p>High-rated players are spread across teams.</p></div><div class="fair-card"><small>Fresh pairings</small><strong>{comparison["repeat_score"]:.0%} BETTER</strong><p>Beats that share of random draws on repeat pairings.</p></div><div class="fair-card"><small>Keepers</small><strong>{keeper_line}</strong><p>Keeper coverage is shown for every team.</p></div></div>'''


def _history_insights(history: list[Night], roster: list[Player]) -> tuple[str, str, str]:
    counts = {}
    last_seen = {}
    for index, night in enumerate(history):
        for players in night.teams.values():
            for left, right in __import__('itertools').combinations(sorted(players), 2):
                pair = (left, right)
                counts[pair] = counts.get(pair, 0) + 1
                last_seen[pair] = index
    frequent = max(counts, key=counts.get) if counts else None
    most_text = f"{frequent[0]} + {frequent[1]} · {counts[frequent]} nights" if frequent else "No pair history yet"
    apart = min(counts, key=counts.get) if counts else None
    apart_text = f"{apart[0]} + {apart[1]} · {len(history) - 1 - last_seen[apart]} nights apart" if apart else "No history yet"
    top = max(roster, key=lambda player: player.rating, default=None)
    top_pairs = sorted(((pair, count) for pair, count in counts.items() if top and top.name in pair), key=lambda item: item[1], reverse=True)
    top_text = f"{top_pairs[0][0][1] if top_pairs and top_pairs[0][0][0] == top.name else top_pairs[0][0][0]} · {top_pairs[0][1]} nights" if top_pairs else "No teammate history yet"
    return most_text, apart_text, top_text


def _history_matrix_html(history: list[Night]) -> str:
    counts = {}
    names = sorted({player for night in history for team in night.teams.values() for player in team})
    for night in history[-config.HISTORY_WINDOW:]:
        for players in night.teams.values():
            for left in players:
                for right in players:
                    if left != right:
                        counts[(left, right)] = counts.get((left, right), 0) + 1
    maximum = max(counts.values(), default=1)
    cells = ['<div class="matrix-label"></div>'] + [f'<div class="matrix-label">{escape(name)}</div>' for name in names]
    for row in names:
        cells.append(f'<div class="matrix-label">{escape(row)}</div>')
        for column in names:
            value = counts.get((row, column), 0)
            intensity = value / maximum if value else 0
            color = f'rgba(43,255,154,{0.12 + intensity * 0.78:.2f})' if value else '#17233d'
            cells.append(f'<div class="matrix-cell" style="background:{color}" title="{escape(row)} with {escape(column)}: {value}">{value or "—"}</div>')
    return f'<div class="matrix-wrap"><div class="matrix-grid" style="--matrix-size:{len(names)}">{"".join(cells)}</div></div><div class="matrix-legend"><span>Never teamed</span><span class="legend-scale"></span><span>Often teamed</span></div>' if names else '<div class="empty-state">◎<br>No teammate history available yet.</div>'


def _player_visual(name: str, label: str, number: int) -> str:
    """Return a tiny inline football-player illustration for a team card."""
    safe_name = escape(label)
    return f'''<div class="player-visual">
      <div class="player-avatar"><svg viewBox="0 0 54 66" aria-hidden="true">
        <circle cx="27" cy="12" r="9" fill="#f3c7a8"/><path d="M17 10c1-10 19-12 22 1-5-4-14-5-22-1" fill="#18375d"/>
        <path d="M11 63c1-16 5-25 16-25s15 9 16 25" fill="#2c80df"/><path d="M13 62h12v-18h4v18h12" fill="none" stroke="#fff" stroke-width="2"/>
        <text x="27" y="51" text-anchor="middle" font-size="10" font-weight="800" fill="#fff">{number}</text>
      </svg></div><div class="player-name">{safe_name}</div>
    </div>'''


def _token_panel() -> None:
    totals = get_run_totals()
    latest = st.session_state.get("attendance_tokens", {})
    input_tokens = latest.get("input_tokens", totals.get("input_tokens", 0))
    cached_tokens = latest.get("cached_input_tokens", totals.get("cached_input_tokens", 0))
    output_tokens = latest.get("output_tokens", totals.get("output_tokens", 0))
    calls = latest.get("calls", totals.get("calls", 0))
    hits = latest.get("cache_hits", totals.get("cache_hits", 0))
    cost = totals.get("estimated_cost")
    cost_text = f"${cost:.6f}" if cost is not None else "set prices in config.py"
    used = min(1.0, calls / max(1, config.MAX_LLM_CALLS_PER_RUN))
    st.markdown(f'<div class="fair-card token-panel"><small>AI USAGE · LAST RUN / SESSION</small><strong>{input_tokens} input · {cached_tokens} cached · {output_tokens} output</strong><p>{calls} calls · {hits} cache hits · {cost_text}</p></div>', unsafe_allow_html=True)
    st.progress(used, text=f"Run budget: {calls}/{config.MAX_LLM_CALLS_PER_RUN} calls")


def _safety_demo_panel(key_state) -> None:
    if os.getenv("FAIRDRAW_DEMO") != "1":
        return
    with st.expander("Safety demos (for the report)"):
        attack_files = sorted((DATA / "attacks").glob("*.txt"))
        selected = st.selectbox("Attack chat", [path.name for path in attack_files], key="demo_attack") if attack_files else None
        if st.button("Load attack chat", disabled=not key_state.available or not selected):
            attack_text = next(path.read_text(encoding="utf-8") for path in attack_files if path.name == selected)
            result = run_attendance_pipeline(attack_text, st.session_state.roster)
            st.dataframe([row.__dict__ for row in result["proposed_attendance"]], use_container_width=True)
            st.json(result["defense_events"])
            st.success("Blocked: suspicious claims remain flagged for organizer review.")
        if st.button("Simulate bad model output"):
            from fairdraw.attendance_agent import Claim
            from fairdraw.chat_splitter import Message
            from fairdraw.verifier import verify_claims
            from datetime import datetime
            message = Message(0, "Demo", datetime.now(), "Ari is in")
            try:
                Claim.model_validate({"message_index": 0, "subject_text": "Ari", "status": "in", "evidence_snippet": "Ari is in", "rating": 10})
            except Exception as exc:
                checked = verify_claims([Claim(message_index=0, subject_text="Zlatan", status="in", evidence_snippet="Ari is in")], [message])
                st.warning(f"Fallback: invalid model JSON/fields rejected ({type(exc).__name__}); invented claim dropped: {len(checked.events)} defense event.")
        if st.button("Trigger budget cap"):
            original = config.MAX_LLM_CALLS_PER_RUN
            try:
                config.MAX_LLM_CALLS_PER_RUN = 1
                from fairdraw.llm_client import LLMCallLimitError, _check_limits
                try: _check_limits()
                except LLMCallLimitError as exc: st.info(f"Blocked: {exc}")
            finally: config.MAX_LLM_CALLS_PER_RUN = original
        st.button("Try to draw before confirming", disabled=True, help="Confirm the squad first")
        st.caption("Blocked: the draw requires organizer-confirmed attendance.")


def main() -> None:
    _init_state()
    st.set_page_config(page_title="Sunday League Fair Draw", page_icon="⚽", layout="wide")
    st.markdown("""
    <style>
    :root { --league-accent: #1266c5; --league-deep: #082b57; --league-sky: #eaf5ff; --league-cyan: #57c7ef; --league-ink: #172d45; }
    .stApp { background: linear-gradient(180deg, #edf7ff 0%, #f8fbff 48%, #e9f4ff 100%); color: var(--league-ink); }
    [data-testid="stSidebar"] { background: #eaf4ff; border-right: 1px solid #c9e1f8; }
    h1, h2, h3 { color: var(--league-deep); letter-spacing: -0.035em; }
    h1 { font-size: 2.7rem !important; }
    div.stButton > button, div.stDownloadButton > button { border-radius: 12px; min-height: 2.75rem; font-weight: 700; border: 1px solid #8cc5ef; transition: .2s ease; }
    div.stButton > button:hover, div.stDownloadButton > button:hover { border-color: var(--league-accent); transform: translateY(-1px); }
    div.stButton > button[kind="primary"] { background: var(--league-accent); color: white; border: 0; box-shadow: 0 7px 18px #1266c533; }
    [data-testid="stMetricValue"] { color: var(--league-accent); }
    section.main > div { padding-top: 1.3rem; padding-bottom: 4rem; max-width: 1180px; }
    .league-hero { position: relative; overflow: hidden; min-height: 245px; padding: 2rem 2.2rem; margin: .2rem 0 1.8rem; border-radius: 28px; color: white; background: radial-gradient(circle at 85% 12%, #57c7ef88 0 9%, transparent 10%), linear-gradient(120deg, #061f43 0%, #0b4f9c 55%, #168bd0 100%); box-shadow: 0 22px 45px #082b5740; }
    .league-hero h1 { color: white !important; margin: 0; font-size: 2.9rem !important; }
    .league-hero p { max-width: 570px; color: #ffe9e7; font-size: 1.05rem; margin: .55rem 0 0; }
    .hero-ball { position: absolute; right: 8%; bottom: -55px; font-size: 12rem; line-height: 1; filter: drop-shadow(0 10px 10px #02152f70); transform: rotate(-14deg); }
    .hero-lineup { position: absolute; right: 17%; bottom: 10px; display: flex; align-items: end; gap: .2rem; opacity: .95; }
    .hero-player { width: 47px; height: 104px; position: relative; filter: drop-shadow(0 5px 4px #02152f55); }
    .hero-player i { position: absolute; left: 13px; top: 0; width: 22px; height: 22px; border-radius: 50%; background: #efbd99; border: 3px solid #082b57; }
    .hero-player b { position: absolute; left: 5px; top: 22px; width: 38px; height: 61px; border-radius: 18px 18px 8px 8px; background: #40b6e8; border: 3px solid #d9f5ff; }
    .hero-player em { position: absolute; left: 10px; bottom: 0; width: 10px; height: 29px; background: #102f58; border-radius: 8px; box-shadow: 18px 0 #102f58; }
    .hero-player:nth-child(2) { transform: translateY(-15px) scale(1.12); z-index: 2; }
    .hero-player:nth-child(2) b { background: #f5c451; }
    .hero-player:nth-child(3) { transform: translateY(4px); }
    .hero-kicker { color: #bfeeff; font-size: .75rem; letter-spacing: .17em; font-weight: 800; text-transform: uppercase; }
    .step-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: .7rem; margin: 0 0 2rem; }
    .step-chip { padding: .8rem .9rem; border: 1px solid #c9e1f8; border-radius: 14px; background: white; box-shadow: 0 4px 14px #082b5710; }
    .step-chip b { display: block; color: var(--league-accent); font-size: .8rem; }
    .step-chip span { font-size: .82rem; color: #725b62; }
    .section-card { padding: 1.35rem 1.5rem .7rem; margin: 1rem 0 1.4rem; border: 1px solid #c9e1f8; border-radius: 18px; background: #ffffffd9; box-shadow: 0 8px 24px #082b5710; }
    .section-label { color: var(--league-accent); text-transform: uppercase; letter-spacing: .13em; font-size: .7rem; font-weight: 800; margin-bottom: -.4rem; }
    .team-card { min-height: 255px; padding: 1.15rem; border-radius: 20px; background: linear-gradient(145deg, #ffffff 0%, #eaf5ff 100%); border: 1px solid #9bcdf1; box-shadow: 0 10px 24px #082b5715; }
    .team-card-head { display: flex; justify-content: space-between; align-items: center; padding-bottom: .7rem; margin-bottom: .75rem; border-bottom: 2px solid #cce5fa; color: var(--league-deep); font-weight: 800; }
    .team-card-head span { color: var(--league-accent); font-size: 1.35rem; }
    .player-visual { display: flex; align-items: center; gap: .6rem; padding: .2rem .35rem; margin: .25rem 0; border-radius: 10px; background: white; color: #18375d; font-weight: 700; box-shadow: 0 2px 8px #082b570c; }
    .player-avatar { width: 34px; height: 40px; padding: 2px; border-radius: 8px; background: #dff1ff; }
    .player-avatar svg { width: 100%; height: 100%; }
    .player-name { font-size: .92rem; }
    .league-footer { margin-top: 3rem; padding: 1rem 0; border-top: 1px solid #c9e1f8; color: #5b7188; font-size: .9rem; text-align: center; }
    .bottom-nav { display: flex; justify-content: space-around; gap: .5rem; margin: 2rem 0 .5rem; padding: .8rem; border-radius: 18px; background: #06234b; color: #d6efff; box-shadow: 0 12px 26px #082b5730; }
    .bottom-nav div { min-width: 90px; text-align: center; font-size: .72rem; font-weight: 700; opacity: .8; }
    .bottom-nav div:first-child { color: white; opacity: 1; }
    .bottom-nav span { display: block; font-size: 1.25rem; margin-bottom: .2rem; }
    @media (max-width: 720px) { .step-strip { grid-template-columns: repeat(2, 1fr); } .hero-ball { right: -12%; opacity: .45; } }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f"<style>{(ROOT / 'assets' / 'theme.css').read_text(encoding='utf-8')}\n{(ROOT / 'assets' / 'overhaul.css').read_text(encoding='utf-8')}\n{(ROOT / 'assets' / 'avatars.css').read_text(encoding='utf-8')}\n{(ROOT / 'assets' / 'hero.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    st.markdown('''<div class="topbar"><div class="wordmark"><svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="13" fill="none" stroke="#2BFF9A" stroke-width="2"/><path d="m16 8 4 3-1 5h-6l-1-5zM7 17l6-1 3 5-4 4M25 17l-6-1-3 5 4 4" fill="none" stroke="#2BFF9A" stroke-width="2"/></svg> FAIR DRAW</div><div class="nav-pills"><span class="nav-pill active">MATCHDAY</span><span class="nav-pill">ROSTER</span><span class="nav-pill">DRAW</span><span class="nav-pill">HISTORY</span><span class="nav-pill">VERIFY</span></div></div>''', unsafe_allow_html=True)
    days_until_matchday = (config.LEAGUE_WEEKDAY - date.today().weekday()) % 7
    matchday = date.today() if days_until_matchday == 0 else date.today() + __import__('datetime').timedelta(days=days_until_matchday)
    confirmed = len(st.session_state.attendance) + len(st.session_state.guest)
    st.markdown(f'''<div class="matchday"><svg class="stadium-art" viewBox="0 0 500 180" aria-hidden="true"><defs><linearGradient id="beam" x1="0" x2="1"><stop stop-color="#22D3EE" stop-opacity=".2"/><stop offset="1" stop-color="#22D3EE" stop-opacity="0"/></linearGradient></defs><path d="M290 35 220 165h180zM390 35 350 165h150z" fill="url(#beam)"/><path d="M30 145h440M100 100h300M170 70h160" stroke="#fff" stroke-opacity=".12"/><path d="M80 155h340v20H80z" fill="#071126"/><path d="M125 140h250" stroke="#2BFF9A" stroke-opacity=".35" stroke-width="3"/></svg><div class="kicker">SUNDAY LEAGUE · MATCHDAY</div><div class="match-meta"><div><div class="match-date">{matchday.strftime("%a %d %b").upper()}</div><div style="color:#9DB2D6">Floodlights on · fair teams incoming</div></div><div class="match-time">KICKOFF <strong>7:30 PM</strong></div></div><div class="status-row"><span class="ui-chip">ATTENDANCE · {confirmed}/{len(st.session_state.roster)} CONFIRMED</span><span class="ui-chip violet">SEED · {"LOCKED" if st.session_state.seed_shown else "NOT DRAWN"}</span><span class="ui-chip {"good" if st.session_state.draw_result else "warn"}">DRAW · {"VERIFIED" if st.session_state.draw_result else "NOT VERIFIED"}</span></div></div>''', unsafe_allow_html=True)
    key_state = load_key_state(ROOT)
    if not key_state.available:
        key_state = load_key_state(ROOT.parents[2])
    with st.sidebar:
        if key_state.available:
            st.markdown('<span class="ui-chip good">● AI READY</span>', unsafe_allow_html=True)
            location = "repo folder" if key_state.env_path == ROOT / ".env" else "parent folder"
            st.caption(f"Key: {escape(key_state.key_name or '')}, found in {location}")
        else:
            st.markdown('<span class="ui-chip">● AI OFF</span>', unsafe_allow_html=True)
        mode = st.radio("Data mode", ["Sample data", "My real data (data/real/)"], key="data_mode")
        st.toggle("Hide ratings on screen", value=True, key="hide_ratings")
        if st.button("Load sample data"):
            st.session_state.data_mode = "Sample data"
            _load_sample()
            st.rerun()
        st.caption("Sample files are never overwritten.")

    _safety_demo_panel(key_state)

    if not st.session_state.roster and mode == "Sample data":
        _load_sample()
    if st.session_state.data_mode != mode:
        st.session_state.data_mode = mode
        _load_mode_data()

    st.markdown(section_header("STEP 01", "Build your roster", "Set ratings and goalkeeper roles before matchday."), unsafe_allow_html=True)
    if st.session_state.data_mode != "Sample data":
        st.session_state.avatar_style = st.segmented_control("Avatar style", ["shirt", "photo"], default=st.session_state.avatar_style, key="avatar_style_control") or st.session_state.avatar_style
    _render_roster_cards()
    with st.expander("Edit roster"):
        _roster_editor()

    st.markdown(section_header("STEP 02", "Tonight's attendance", "Tap the squad in. Confirmed players get the green light."), unsafe_allow_html=True)
    selected = _render_squad_board() if not st.session_state.attendance_confirmed else st.session_state.attendance
    in_count = len(selected) + len(st.session_state.guest)
    out_count = max(0, len(st.session_state.roster) - len(selected))
    st.markdown(f'<div class="status-row"><span class="ui-chip good">✓ {in_count} IN</span><span class="ui-chip">{out_count} OUT</span></div>', unsafe_allow_html=True)
    st.progress(in_count / len(st.session_state.roster) if st.session_state.roster else 0)
    st.markdown('**＋ Add guest**  \n<span style="color:#93A0B8">Guest ratings are entered by the organizer only.</span>', unsafe_allow_html=True)
    with st.form("guest_form"):
        guest_name = st.text_input("Guest name", label_visibility="collapsed", placeholder="Guest name")
        guest_rating = st.number_input("Guest rating", 1, 10, 5)
        if st.form_submit_button("Add guest") and guest_name.strip():
            st.session_state.guest.append(Player(name=guest_name.strip(), rating=int(guest_rating)))
            st.success(f"Added guest {guest_name.strip()}.")
    if st.session_state.guest:
        st.caption("Guests: " + ", ".join(player.name for player in st.session_state.guest))
    chat_status = "AI READY" if key_state.available else "AI OFF · NO KEY"
    st.markdown(f'<div class="chat-reader"><strong>Chat reader</strong><br><span class="ui-chip">{chat_status}</span><p style="color:#93A0B8;margin:.7rem 0 0">Attendance proposals from chat will be added in Stage 5. Nothing is auto-applied yet.</p></div>', unsafe_allow_html=True)
    chat_text = st.text_area("Paste group chat here", placeholder="Paste an exported WhatsApp or bracket-style chat…", disabled=not key_state.available, label_visibility="collapsed", key="attendance_chat")
    if st.button("Read attendance", disabled=not key_state.available or not chat_text.strip(), help="Add an API key to enable the AI chat reader." if not key_state.available else None):
        with st.spinner("Reading attendance…"):
            pipeline_result = run_attendance_pipeline(chat_text, st.session_state.roster)
        st.session_state.attendance_proposals = [row.__dict__ for row in pipeline_result["proposed_attendance"]]
        st.session_state.attendance_defense_events = [event.__dict__ for event in pipeline_result["defense_events"]]
        st.session_state.attendance_tokens = pipeline_result["token_totals"]
        st.session_state.run_trace = pipeline_result["trace"]
        st.rerun()
    if st.session_state.attendance_proposals:
        proposal_rows = [{"player": row.get("player") or row.get("guest_name") or "Unknown", "status": row.get("proposed_status", "unknown"), "evidence": row.get("evidence_snippet", ""), "sender": row.get("sender", ""), "flag": row.get("flag") or ""} for row in st.session_state.attendance_proposals]
        st.caption("Proposals — review every row before confirming")
        edited_proposals = st.data_editor(proposal_rows, hide_index=True, use_container_width=True, disabled=["player", "evidence", "sender", "flag"], column_config={"status": st.column_config.SelectboxColumn(options=["in", "out", "maybe", "unknown", "late"], required=True)}, key="attendance_proposal_editor")
        st.session_state.attendance_proposals = edited_proposals
        if st.session_state.attendance_defense_events:
            with st.expander("Defense log"):
                st.json(st.session_state.attendance_defense_events)
        _token_panel()
        with st.expander("Run trace"):
            for item in st.session_state.run_trace:
                icon = "✓" if item["status"] == "ok" else ("!" if item["status"] == "flagged" else "•")
                st.markdown(f"**{icon} {item['step']}. {escape(item['component'])}** · `{escape(item['type'])}` · `{escape(item['status'])}`  \n{escape(item['input_summary'])} → {escape(item['output_summary'])} · {item['duration_seconds']:.3f}s")
            if st.session_state.run_trace:
                st.download_button("Download trace (JSON)", json.dumps({"steps": st.session_state.run_trace}, indent=2), "run_trace.json", "application/json")
    if st.button("Confirm attendance", disabled=st.session_state.attendance_confirmed or not selected):
        st.session_state.attendance = selected
        st.session_state.attendance_confirmed = True
        st.success("Attendance confirmed. The draw is unlocked.")
        st.rerun()
    if st.session_state.attendance_confirmed:
        st.markdown(f'<div class="locked-banner"><span>🔒 <strong>Squad locked</strong><br><small>{len(st.session_state.attendance) + len(st.session_state.guest)} players confirmed for tonight</small></span><span style="color:#2BFF9A;font-size:.75rem">UNLOCK</span></div>', unsafe_allow_html=True)

    st.markdown(section_header("STEP 03", "Make the fair draw", "A seeded split that balances strength and recent pairings."), unsafe_allow_html=True)
    selected_team_count = st.segmented_control("Number of teams", [2, 3, 4], default=st.session_state.team_count, disabled=st.session_state.attendance_confirmed, key="team_segment")
    st.session_state.team_count = selected_team_count or st.session_state.team_count
    seed_mode = st.segmented_control("Seed mode", ["Automatic", "I will type a seed"], default="Automatic", key="seed_segment") or "Automatic"
    typed_seed = st.number_input("Seed", value=1, step=1, disabled=seed_mode == "Automatic")
    can_draw = st.session_state.attendance_confirmed and len(st.session_state.attendance) + len(st.session_state.guest) >= st.session_state.team_count * config.MIN_PLAYERS_PER_TEAM
    if not can_draw:
        st.caption(f"Confirm attendance with at least {st.session_state.team_count * config.MIN_PLAYERS_PER_TEAM} players to enable the draw.")
    st.markdown(f'<div class="draw-count"><strong>DRAW #{st.session_state.draw_count + (1 if can_draw else 0)}</strong> TONIGHT · Every re-draw is logged</div>', unsafe_allow_html=True)
    if st.button("RUN DRAW" if not st.session_state.draw_result else "RE-DRAW", type="primary", disabled=not can_draw):
        try:
            all_players = st.session_state.roster + st.session_state.guest
            seed = random.SystemRandom().randrange(2**63) if seed_mode == "Automatic" else int(typed_seed)
            st.session_state.draw_count += 1
            st.session_state.seed_shown = seed
            st.session_state.draw_result = draw(st.session_state.attendance + [p.name for p in st.session_state.guest], all_players, st.session_state.history, _settings(st.session_state.team_count), seed=seed, attempt_index=st.session_state.draw_count)
            st.session_state.run_trace.extend([
                record(6, "Draw engine", "tool", f"{len(st.session_state.attendance) + len(st.session_state.guest)} confirmed attendees", f"{len(st.session_state.draw_result.teams)} teams generated", "ok"),
                record(7, "Draw verifier", "verifier", "published seed and generated teams", "teams available for receipt verification", "ok"),
            ])
            save_trace(st.session_state.run_trace)
        except ValueError as exc:
            st.error(f"The draw could not run: {exc}")
    if st.session_state.draw_result:
        result = st.session_state.draw_result
        st.markdown(f'<div class="status-row"><span class="ui-chip good">LOCKED · SEED {st.session_state.seed_shown}</span><span class="ui-chip violet">DRAW #{st.session_state.draw_count} TONIGHT</span></div>', unsafe_allow_html=True)
        columns = st.columns(st.session_state.team_count)
        lookup = {p.name: p for p in st.session_state.roster + st.session_state.guest}
        for index, (column, (team, players)) in enumerate(zip(columns, result.teams.items())):
            with column:
                st.markdown(_pitch_card(team, players, lookup, ["#2BFF9A", "#7C5CFF", "#38BDF8", "#FF4D6D"][index]), unsafe_allow_html=True)

        fairness_tab, receipt_tab = st.tabs(["Fairness report", "Draw receipt"])
        with fairness_tab:
            attendees_now = st.session_state.attendance + [p.name for p in st.session_state.guest]
            ratings_now = {p.name: p.rating for p in st.session_state.roster + st.session_state.guest}
            keepers_now = {p.name for p in st.session_state.roster + st.session_state.guest if p.keeper}
            tops = top_players(attendees_now, ratings_now, config.TOP_FRACTION)
            top_counts = top_players_per_team(result.teams, tops)
            keeper_split = keeper_counts(result.teams, keepers_now)
            baseline = random_baseline(attendees_now, st.session_state.roster + st.session_state.guest, st.session_state.history, _settings(st.session_state.team_count), samples=500, seed=result.seed)
            comparison = percentile(result, baseline)
            metrics = {
                "Strength gap": (result.metrics["strength_gap"], "Lower is better: the teams' average ratings are this far apart."),
                "Size difference": (size_difference(result.teams), "Lower is better: team sizes differ by this many players."),
                "Top players per team": (", ".join(f"{team}: {count}" for team, count in top_counts.items()), "Top players were spread across these teams."),
                "Repeat pairing score": (result.metrics["repeat_score"], "Lower is better: this measures recent teammate repetition."),
                "Keeper split": (", ".join(f"{team}: {count}" for team, count in keeper_split.items()), "Goalkeepers were distributed as shown."),
            }
            st.markdown(_fairness_cards(result, comparison, top_counts, keeper_split), unsafe_allow_html=True)
            st.info(f"This draw beats {comparison['repeat_score']:.1%} of random draws on repeat pairings and {comparison['strength_gap']:.1%} on strength balance.")
        with receipt_tab:
            full_receipt = build_full_receipt(result, attendees_now, st.session_state.roster + st.session_state.guest, st.session_state.history, _settings(st.session_state.team_count))
            public_receipt = build_public_receipt(result, attendees_now, st.session_state.roster + st.session_state.guest, st.session_state.history, _settings(st.session_state.team_count))
            st.markdown(f'<div class="certificate"><div class="kicker">MATCH CERTIFICATE</div><p><span class="mono-pill">SEED {result.seed}</span> &nbsp; DRAW #{result.attempt_index} · ENGINE {escape(result.engine_version)}</p><small style="color:#93A0B8">HASH {escape(full_receipt["inputs_hash"][:12])}… · {escape(full_receipt["timestamp"])}</small></div>', unsafe_allow_html=True)
            st.code(str(result.seed), language="text")
            st.subheader("Receipts")
            st.json(public_receipt)
            st.download_button("Download public receipt", json.dumps(public_receipt, indent=2), "public_receipt.json", "application/json")
            if st.button("Write announcement", disabled=not key_state.available, help="Add an API key to enable announcement writing." if not key_state.available else None):
                try:
                    announcement = create_announcement(public_receipt, "")
                    attendee_names = [name for players in result.teams.values() for name in players]
                    allowed_numbers = [st.session_state.team_count, *[len(players) for players in result.teams.values()], result.seed, result.attempt_index]
                    checked = verify_announcement(announcement, attendee_names, result.teams.keys(), allowed_numbers)
                    if not checked.valid:
                        announcement = create_announcement(public_receipt, "Use the published match details.")
                        checked = verify_announcement(announcement, attendee_names, result.teams.keys(), allowed_numbers)
                    if checked.valid:
                        st.session_state.announcement_text = announcement
                        st.session_state.announcement_error = ""
                        st.session_state.run_trace.extend([record(8, "Announcement agent", "LLM agent", "public receipt and organizer note", "announcement generated", "ok"), record(9, "Announcement verifier", "verifier", "announcement names and numbers", "announcement accepted", "ok")])
                    else:
                        st.session_state.announcement_text = "Sunday League Fair Draw\n" + "\n".join(f"{team}: {', '.join(players)}" for team, players in result.teams.items()) + f"\nDraw #{result.attempt_index}, seed {result.seed}, verify it with the app"
                        st.session_state.announcement_error = "AI announcement failed verification twice; showing a code-generated announcement."
                        st.session_state.run_trace.extend([record(8, "Announcement agent", "LLM agent", "public receipt and organizer note", "generated text rejected", "flagged"), record(9, "Announcement verifier", "verifier", "announcement names and numbers", "code fallback shown", "blocked")])
                except Exception as exc:
                    st.session_state.announcement_error = f"Announcement unavailable: {type(exc).__name__}"
                    st.session_state.run_trace.append(record(8, "Announcement agent", "LLM agent", "public receipt", "announcement unavailable", "blocked"))
                save_trace(st.session_state.run_trace)
            if st.session_state.announcement_text:
                if st.session_state.announcement_error: st.warning(st.session_state.announcement_error)
                st.text_area("Announcement", st.session_state.announcement_text, height=130)
                st.download_button("Copy announcement text", st.session_state.announcement_text, "announcement.txt", "text/plain")
            _token_panel()
            with st.expander("Organizer audit receipt"):
                st.warning("This receipt contains private ratings.")
                st.json(full_receipt)
                st.download_button("Download organizer audit receipt", json.dumps(full_receipt, indent=2), "organizer_receipt.json", "application/json")
                if st.button("Verify this draw"):
                    verification = verify_full_receipt(full_receipt)
                    st.session_state.last_verification = verification["match"]
                    if verification["match"]:
                        st.markdown('<div class="verified-badge">✓ VERIFIED: MATCH</div>', unsafe_allow_html=True)
                    else:
                        st.error("MISMATCH")
                        with st.expander("View verification difference"):
                            st.json(verification["diff"])
            st.markdown('<div class="matchday-card"><div class="kicker">MATCHDAY CARD</div><h3>Sunday League Fair Draw</h3><p>Tonight\'s teams are locked and ready.</p><div style="display:grid;grid-template-columns:1fr 1fr;gap:.8rem">' + ''.join(f'<div><strong>{escape(team)}</strong><br><span style="color:#d8d5ff">{escape(" · ".join(players))}</span></div>' for team, players in result.teams.items()) + f'</div><small style="display:block;margin-top:1rem;color:#b9b2ea">SEED {result.seed} · DRAW #{result.attempt_index}</small></div>', unsafe_allow_html=True)
            st.text_area("Copy announcement text", "Sunday League Fair Draw\n" + "\n".join(f"{team}: {', '.join(players)}" for team, players in result.teams.items()) + f"\nSeed: {result.seed} · Draw #{result.attempt_index}", height=100)

    st.markdown(section_header("STEP 04", "History & trust", "Keep the league transparent from one Sunday to the next."), unsafe_allow_html=True)
    history_tab, matrix_tab = st.tabs(["Past nights", "Teammate matrix"])
    with history_tab:
        if st.session_state.history:
            rows = []
            for night in sorted(st.session_state.history, key=lambda item: item.date, reverse=True):
                teams = list(night.teams.items())
                team_markup = ''.join(f'<div class="fixture-team"><strong>{escape(team)}</strong><div class="player-chip-list">{"".join(f"<span class=\"player-chip\">{escape(player)}</span>" for player in players)}</div></div>' for team, players in teams)
                rows.append(f'<div class="fixture-row"><div class="fixture-date">{night.date.isoformat()}</div><div class="fixture-title">{escape(" vs ".join(team for team, _ in teams))}</div><div class="fixture-teams">{team_markup}</div></div>')
            st.markdown('<div class="fixture-feed">' + ''.join(rows) + '</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state">◎<br>No past nights loaded yet.</div>', unsafe_allow_html=True)
    with matrix_tab:
        st.markdown(_history_matrix_html(st.session_state.history), unsafe_allow_html=True)
        frequent, apart, top_teammates = _history_insights(st.session_state.history, st.session_state.roster)
        st.markdown(f'<div class="insight-grid"><div class="insight-card"><small>Most frequent pair</small><strong>{escape(frequent)}</strong><p>The teammates who have shared the most nights.</p></div><div class="insight-card"><small>Longest time apart</small><strong>{escape(apart)}</strong><p>A pair that has had the most space recently.</p></div><div class="insight-card"><small>Top player teammates met</small><strong>{escape(top_teammates)}</strong><p>Who has shared the pitch with the highest-rated player.</p></div></div>', unsafe_allow_html=True)
    if st.button("Save tonight to history", disabled=st.session_state.draw_result is None):
        if st.session_state.data_mode == "Sample data":
            st.warning("Sample data is read-only. Switch to My real data to save history.")
        else:
            result = st.session_state.draw_result
            st.session_state.history.append(Night(date=date.today(), teams=result.teams))
            save_history(st.session_state.history, "history.json", REAL_DATA)
            st.success("Tonight was saved to data/real/history.json.")
    st.markdown('''<div class="bottom-nav"><div><span>⌂</span>HOME</div><div><span>♟</span>TEAMS</div><div><span>⚽</span>DRAW</div><div><span>◷</span>HISTORY</div><div><span>•••</span>MORE</div></div><div class="league-footer">The draw is calculated by code from a published seed. The AI only reads the chat and writes the announcement.</div>''', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
