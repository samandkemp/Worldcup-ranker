"""Streamlit dashboard for World Cup 2026 player & team analysis."""
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow `streamlit run src/worldcup_ranker/webapp.py` from the project root
_src = Path(__file__).resolve().parents[1]
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import streamlit as st

from worldcup_ranker import analytics
from worldcup_ranker.pipeline import fetch_for_leagues, enrich_with_tournament_stats
from worldcup_ranker.storage import Storage
from worldcup_ranker.ingest.wiki_adapter import fetch_groups_from_wikipedia
from worldcup_ranker.ingest.soccerdata_adapter import fetch_tournament_stats

# ── Constants ─────────────────────────────────────────────────────────────────

WC2026_WIKI_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"
WC2026_MAIN_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup"

_TOP_LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "GER-Bundesliga",
    "ITA-Serie A",
    "FRA-Ligue 1",
    "POR-Primeira Liga",
    "NED-Eredivisie",
]
_ALL_LEAGUES = _TOP_LEAGUES + [
    "BEL-First Division A",
    "TUR-Super Lig",
    "SCO-Premiership",
    "USA-MLS",
    "BRA-Serie A",
    "ARG-Liga Profesional",
    "SAU-Saudi Professional League",
]

# Six axes used on all radar charts
_RADAR_AXES   = ["goals_per90", "xG_per90", "assists_per90", "xA_per90", "overall", "rating"]
_RADAR_LABELS = ["Goals/90", "xG/90", "Assists/90", "xA/90", "Overall", "Rating"]
_AXIS_LABEL   = dict(zip(_RADAR_AXES, _RADAR_LABELS))

# Position-appropriate axes — GKs don't score, defenders rarely do
_POS_AXES: Dict[str, List[str]] = {
    "GK":      ["overall", "rating"],
    "DEF":     ["assists_per90", "xA_per90", "overall", "rating"],
    "MID":     _RADAR_AXES,
    "FWD":     _RADAR_AXES,
    "Unknown": _RADAR_AXES,
}
_POS_LABELS = _AXIS_LABEL  # re-use the same label map

_DATA_DIR = str(Path(__file__).resolve().parents[2] / "data")


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _safe(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        f = float(v)
        return default if math.isnan(f) else f
    except Exception:
        return default


def _time_ago(iso: str) -> str:
    try:
        delta = datetime.now() - datetime.fromisoformat(iso)
        mins = int(delta.total_seconds() / 60)
        if mins < 1:
            return "just now"
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return iso


def _apply_min_minutes(
    squads: Dict[str, List[Dict]], min_minutes: int
) -> Dict[str, List[Dict]]:
    if min_minutes <= 0:
        return squads
    return {
        country: [p for p in profiles if _safe((p.get('aggregated') or {}).get('minutes')) >= min_minutes]
        for country, profiles in squads.items()
    }


def _get_position(profile: Dict) -> str:
    return analytics._extract_position_from_profile(profile)


# ── Normalisation ─────────────────────────────────────────────────────────────

def _axis_ranges(profiles: List[Dict], axes: List[str]) -> Dict[str, Tuple[float, float]]:
    ranges: Dict[str, Tuple[float, float]] = {}
    for a in axes:
        vals = []
        for p in profiles:
            v = analytics.per90_metrics(p).get(a)
            if v is not None and isinstance(v, (int, float)) and not math.isnan(float(v)):
                vals.append(float(v))
        if len(vals) >= 2:
            mn, mx = min(vals), max(vals)
            ranges[a] = (mn, mx if mx > mn else mn + 1e-6)
        else:
            ranges[a] = (0.0, 1.0)
    return ranges


def _norm(val: float, mn: float, mx: float) -> float:
    return max(0.0, min(1.0, (val - mn) / (mx - mn)))


def _team_avg_row(profiles: List[Dict], top_n: int = 11) -> Dict[str, float]:
    rows = sorted(
        [analytics.per90_metrics(p) for p in profiles],
        key=lambda r: r.get("minutes") or 0,
        reverse=True,
    )[:top_n]
    if not rows:
        return {a: 0.0 for a in _RADAR_AXES}
    return {a: float(sum(_safe(r.get(a)) for r in rows) / len(rows)) for a in _RADAR_AXES}


# ── Radar builders ────────────────────────────────────────────────────────────

def _build_radar(
    traces: List[Tuple[str, List[float]]],
    axes: List[str],
    title: str,
) -> Optional[Any]:
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None
    labels = [_AXIS_LABEL.get(a, a) for a in axes]
    theta = labels + [labels[0]]
    fig = go.Figure()
    for label, vals in traces:
        r = vals + [vals[0]]
        fig.add_trace(go.Scatterpolar(r=r, theta=theta, fill="toself", name=label))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1], tickformat=".0%")),
        title=title,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25),
        margin=dict(t=60, b=80),
    )
    return fig


def _teams_radar(
    pa: List[Dict], pb: List[Dict], la: str, lb: str, all_flat: List[Dict]
) -> Optional[Any]:
    ranges = _axis_ranges(all_flat, _RADAR_AXES)
    traces = []
    for label, profiles in [(la, pa), (lb, pb)]:
        avg = _team_avg_row(profiles)
        vals = [_norm(_safe(avg.get(a)), *ranges[a]) for a in _RADAR_AXES]
        traces.append((label, vals))
    return _build_radar(traces, _RADAR_AXES, f"{la}  vs  {lb}  —  normalised across all squads")


def _players_radar(
    prof_a: Dict,
    prof_b: Dict,
    la: str,
    lb: str,
    all_flat: List[Dict],
    pos_aware: bool = False,
) -> Optional[Any]:
    if pos_aware:
        pos_a = _get_position(prof_a)
        pos_b = _get_position(prof_b)
        # Use the union of both players' position axes so neither loses context
        axes_a = set(_POS_AXES.get(pos_a, _RADAR_AXES))
        axes_b = set(_POS_AXES.get(pos_b, _RADAR_AXES))
        axes = [a for a in _RADAR_AXES if a in axes_a | axes_b]
    else:
        axes = _RADAR_AXES

    ranges = _axis_ranges(all_flat, axes)
    traces = []
    for label, profile in [(la, prof_a), (lb, prof_b)]:
        row = analytics.per90_metrics(profile)
        vals = [_norm(_safe(row.get(a)), *ranges[a]) for a in axes]
        traces.append((label, vals))
    suffix = " (position axes)" if pos_aware else " (all axes)"
    return _build_radar(traces, axes, f"{la}  vs  {lb}  —  normalised across all squads{suffix}")


def _wc_radar(
    prof_a: Dict, prof_b: Dict, la: str, lb: str, all_flat: List[Dict]
) -> Optional[Any]:
    """Radar built from WC tournament stats instead of club stats."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    wc_axes = ["goals_per90", "xG_per90", "assists_per90", "xA_per90"]
    wc_labels = [_AXIS_LABEL[a] for a in wc_axes]

    def _wc_row(profile: Dict) -> Dict[str, float]:
        wc = profile.get('wc_stats') or {}
        mins = max(1, int(wc.get('minutes') or 1))
        return {
            'goals_per90':   float(wc.get('goals') or 0) / mins * 90,
            'xG_per90':      float(wc.get('xG') or 0) / mins * 90,
            'assists_per90': float(wc.get('assists') or 0) / mins * 90,
            'xA_per90':      float(wc.get('xA') or 0) / mins * 90,
            'minutes':       mins,
        }

    all_wc_rows = [_wc_row(p) for profs in
                   [squads.get(t, []) for t in st.session_state.get('squads', {}).keys()]
                   for p in profs if p.get('wc_stats')]

    # Compute normalisation ranges across all players with WC data
    ranges: Dict[str, Tuple[float, float]] = {}
    for a in wc_axes:
        vals = [r[a] for r in all_wc_rows if not math.isnan(r.get(a, math.nan))]
        if len(vals) >= 2:
            mn, mx = min(vals), max(vals)
            ranges[a] = (mn, mx if mx > mn else mn + 1e-6)
        else:
            ranges[a] = (0.0, 1.0)

    theta = wc_labels + [wc_labels[0]]
    fig = go.Figure()
    for label, profile in [(la, prof_a), (lb, prof_b)]:
        row = _wc_row(profile)
        vals = [_norm(row.get(a, 0.0), *ranges[a]) for a in wc_axes]
        fig.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=theta, fill="toself", name=label))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1], tickformat=".0%")),
        title=f"{la}  vs  {lb}  —  WC tournament stats (normalised)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25),
        margin=dict(t=60, b=80),
    )
    return fig


# ── Matchup helpers ───────────────────────────────────────────────────────────

def _vulnerability_bar(vuln: Dict[str, float], team_name: str) -> Optional[Any]:
    """Horizontal bar chart of Team B's defensive vulnerability per axis."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None
    labels = [_AXIS_LABEL.get(a, a) for a in _RADAR_AXES]
    values = [vuln.get(a, 0.0) for a in _RADAR_AXES]
    colours = [
        "#e15759" if v > 0.6 else "#f28e2b" if v > 0.4 else "#59a14f"
        for v in values
    ]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation='h',
        marker_color=colours,
        text=[f"{v:.0%}" for v in values],
        textposition='outside',
    ))
    fig.update_layout(
        title=f"{team_name} — defensive vulnerability by axis",
        xaxis=dict(range=[0, 1.15], tickformat=".0%"),
        height=280,
        margin=dict(l=10, r=40, t=50, b=20),
    )
    return fig


# ── Data tables ───────────────────────────────────────────────────────────────

def _player_stats_df(prof_a: Dict, prof_b: Dict, la: str, lb: str):
    try:
        import pandas as pd
    except ImportError:
        return None

    row_a = analytics.per90_metrics(prof_a)
    row_b = analytics.per90_metrics(prof_b)
    wc_a  = prof_a.get('wc_stats') or {}
    wc_b  = prof_b.get('wc_stats') or {}

    def fmt(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "—"
        return f"{float(v):.3f}" if isinstance(v, (int, float)) else str(v)

    rows = []
    for key, label in [
        ("minutes",      "Club minutes"),
        ("matches",      "Club matches"),
        ("goals",        "Club goals"),
        ("assists",      "Club assists"),
        ("xG",           "Club xG"),
        ("xA",           "Club xA"),
        ("goals_per90",  "Goals / 90"),
        ("assists_per90","Assists / 90"),
        ("xG_per90",     "xG / 90"),
        ("xA_per90",     "xA / 90"),
        ("overall",      "FIFA Overall"),
        ("rating",       "Rating"),
    ]:
        rows.append({"Stat": label, la: fmt(row_a.get(key)), lb: fmt(row_b.get(key))})

    if wc_a or wc_b:
        rows.append({"Stat": "— WC Tournament —", la: "", lb: ""})
        for key, label in [
            ("minutes", "WC minutes"),
            ("matches", "WC matches"),
            ("goals",   "WC goals"),
            ("assists", "WC assists"),
            ("xG",      "WC xG"),
            ("xA",      "WC xA"),
        ]:
            rows.append({"Stat": label, la: fmt(wc_a.get(key)), lb: fmt(wc_b.get(key))})

    return pd.DataFrame(rows).set_index("Stat")


def _rankings_df(squads: Dict[str, List[Dict]], squad_sizes: Dict[str, int]):
    try:
        import pandas as pd
    except ImportError:
        return None
    rows = []
    for country, profiles in sorted(squads.items()):
        if not profiles:
            continue
        agg = analytics.compute_team_aggregates(profiles)
        elo = analytics.team_elo_rating(profiles, all_teams_profiles=squads)
        total = squad_sizes.get(country, len(profiles))
        rows.append({
            "Team": country,
            "Coverage": f"{len(profiles)}/{total}",
            "Strength": round(elo, 1),
            "Goals / 90": round(_safe(agg.get("mean_goals_per90")), 3),
            "Assists / 90": round(_safe(agg.get("mean_assists_per90")), 3),
            "xG / 90": round(_safe(agg.get("weighted_xG_per90")), 3),
            "xA / 90": round(_safe(agg.get("weighted_xA_per90")), 3),
            "Mean Overall": round(_safe(agg.get("mean_overall")), 1),
        })
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("Strength", ascending=False).reset_index(drop=True)
    df.index += 1
    return df


# ── Startup: try to auto-load from cache ──────────────────────────────────────

if "squads" not in st.session_state:
    try:
        _storage = Storage(_DATA_DIR)
        _cache = _storage.load_squads_cache()
        if _cache:
            st.session_state.squads      = _cache['squads']
            st.session_state.squad_sizes = _cache.get('squad_sizes', {})
            st.session_state.fetched_at  = _cache.get('fetched_at')
            st.session_state.fetch_params = {
                'season':   _cache.get('season', '2425'),
                'leagues':  _cache.get('leagues', _TOP_LEAGUES),
                'wiki_url': _cache.get('wiki_url', WC2026_WIKI_URL),
            }
    except Exception:
        pass


# ── Page ──────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="WC2026 Ranker", page_icon="⚽", layout="wide")
st.title("⚽ World Cup 2026 — Team & Player Analysis")


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Data Controls")

    _params = st.session_state.get('fetch_params', {})
    wiki_url = st.text_input(
        "Wikipedia squads URL",
        value=_params.get('wiki_url', WC2026_WIKI_URL),
    )
    season = st.text_input(
        "Season code",
        value=_params.get('season', '2425'),
        help="soccerdata season code — e.g. '2425' = 2024-25",
    )
    selected_leagues = st.multiselect(
        "Leagues to scrape",
        options=_ALL_LEAGUES,
        default=_params.get('leagues', _TOP_LEAGUES),
    )
    force_refresh = st.checkbox("Force refresh (ignore cache)")
    fetch_btn = st.button("Fetch / Refresh Data", type="primary", width='stretch')

    # WC match stats row
    wc_btn = st.button(
        "Fetch WC Match Data",
        width='stretch',
        help="Pull in-tournament stats from FBref and attach to player profiles",
        disabled="squads" not in st.session_state,
    )

    st.divider()

    # Status
    if "squads" in st.session_state:
        n_t = len(st.session_state.squads)
        n_p = sum(len(v) for v in st.session_state.squads.values())
        ts  = st.session_state.get('fetched_at')
        age = f"  ·  {_time_ago(ts)}" if ts else ""
        st.success(f"{n_t} teams · {n_p} players{age}")
        if st.session_state.get('has_wc_stats'):
            st.success("WC match stats loaded")
    else:
        st.info("No data loaded yet.")

    if st.session_state.get('fetch_warnings'):
        with st.expander(f"{len(st.session_state.fetch_warnings)} provider warning(s)"):
            for w in st.session_state.fetch_warnings:
                st.caption(w)

    # Min-minutes filter
    st.divider()
    st.caption("Display filter")
    min_minutes = st.slider(
        "Min. club minutes played",
        min_value=0, max_value=2000, value=500, step=100,
        help="Hides players with less than this many club minutes — reduces noise in charts",
    )

    # Player search
    st.divider()
    st.caption("Quick search")
    search_query = st.text_input("Find a player", placeholder="e.g. Mbappé")


# ── Fetch: club stats ─────────────────────────────────────────────────────────

if fetch_btn:
    if not selected_leagues:
        st.sidebar.error("Select at least one league.")
    else:
        with st.spinner("Fetching club stats — may take a few minutes on first run…"):
            try:
                squads, squad_sizes, warnings = fetch_for_leagues(
                    leagues=selected_leagues,
                    season=season,
                    tournament_wiki_url=wiki_url,
                    storage_path=_DATA_DIR,
                    force_refresh=force_refresh,
                )
                st.session_state.squads       = squads
                st.session_state.squad_sizes  = squad_sizes
                st.session_state.fetch_warnings = warnings
                st.session_state.fetched_at   = datetime.now().isoformat(timespec='seconds')
                st.session_state.has_wc_stats = False
                st.session_state.fetch_params = {
                    'season': season, 'leagues': selected_leagues, 'wiki_url': wiki_url
                }
                st.rerun()
            except Exception as exc:
                st.sidebar.error(f"Fetch failed: {exc}")

# ── Fetch: WC match stats ─────────────────────────────────────────────────────

if wc_btn and "squads" in st.session_state:
    with st.spinner("Fetching WC tournament stats from FBref…"):
        try:
            enriched, wc_warnings = enrich_with_tournament_stats(
                st.session_state.squads,
                tournament="INT-World Cup",
                season="2526",
            )
            st.session_state.squads = enriched
            st.session_state.has_wc_stats = True
            st.session_state.fetch_warnings = (
                st.session_state.get('fetch_warnings', []) + wc_warnings
            )
            # Re-save cache with wc_stats attached
            try:
                _storage = Storage(_DATA_DIR)
                _storage.save_squads_cache(
                    enriched,
                    st.session_state.get('squad_sizes', {}),
                    st.session_state.fetch_params.get('season', season),
                    st.session_state.fetch_params.get('leagues', selected_leagues),
                    st.session_state.fetch_params.get('wiki_url', wiki_url),
                )
            except Exception:
                pass
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"WC stats fetch failed: {exc}")

# ── Guard ─────────────────────────────────────────────────────────────────────

if "squads" not in st.session_state:
    st.info("No squad data loaded. Fetch squad stats using the sidebar controls.")
    st.stop()

# Apply the min-minutes filter for all rendering (doesn't touch session state)
_raw_squads: Dict[str, List[Dict]]   = st.session_state.squads
squads: Dict[str, List[Dict]]        = _apply_min_minutes(_raw_squads, min_minutes)
squad_sizes: Dict[str, int]          = st.session_state.get('squad_sizes', {})
all_flat: List[Dict]                 = [p for profiles in squads.values() for p in profiles]
teams: List[str]                     = sorted(squads.keys())
has_wc_stats: bool                   = st.session_state.get('has_wc_stats', False)

if not teams:
    st.error("No squad data found — Wikipedia URL or provider configuration may be affecting results.")
    st.stop()

# ── Player search results (shown inline when query is non-empty) ───────────────

if search_query:
    q = search_query.strip().lower()
    hits = [
        (p, country)
        for country, profiles in _raw_squads.items()
        for p in profiles
        if q in (p.get('name') or '').lower()
    ]
    if hits:
        st.subheader(f'Search results for "{search_query}"')
        cols = st.columns(min(len(hits), 4))
        for i, (player, country) in enumerate(hits[:8]):
            with cols[i % 4]:
                row = analytics.per90_metrics(player)
                wc  = player.get('wc_stats') or {}
                st.markdown(f"**{player.get('name')}**  \n_{country}_")
                st.caption(
                    f"Goals/90: {_safe(row.get('goals_per90')):.2f}  ·  "
                    f"xG/90: {_safe(row.get('xG_per90')):.2f}  ·  "
                    f"Assists/90: {_safe(row.get('assists_per90')):.2f}"
                )
                if wc:
                    st.caption(
                        f"WC: {int(wc.get('goals',0))}G "
                        f"{int(wc.get('assists',0))}A "
                        f"in {int(wc.get('minutes',0))}min"
                    )
        st.divider()
    else:
        st.info(f'No players found matching "{search_query}".')


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_teams, tab_players, tab_squad, tab_rank, tab_groups, tab_matchup = st.tabs([
    "Team Comparison",
    "Player Comparison",
    "Squad Explorer",
    "Rankings",
    "Group Stage",
    "Matchup",
])


# ═══════════════════════════════════════════════════════
# Tab 1 — Team Comparison
# ═══════════════════════════════════════════════════════

with tab_teams:
    c1, c2 = st.columns(2)
    with c1:
        team_a = st.selectbox("Team A", teams, key="tc_a")
    with c2:
        team_b = st.selectbox("Team B", teams, index=min(1, len(teams) - 1), key="tc_b")

    if team_a == team_b:
        st.warning("Choose two different teams.")
    else:
        pa = squads.get(team_a, [])
        pb = squads.get(team_b, [])

        fig = _teams_radar(pa, pb, team_a, team_b, all_flat)
        if fig:
            st.plotly_chart(fig, width='stretch', key="tc_radar")
        else:
            st.info("Install plotly for the radar chart.")

        st.markdown("#### Aggregated stats")
        mc1, mc2 = st.columns(2)
        for col, label, profiles, team_name in [
            (mc1, team_a, pa, team_a), (mc2, team_b, pb, team_b)
        ]:
            with col:
                total = squad_sizes.get(team_name, len(profiles))
                st.markdown(f"**{label}** — {len(profiles)}/{total} players matched")
                agg = analytics.compute_team_aggregates(profiles)
                st.metric("Goals / 90",          f"{_safe(agg.get('mean_goals_per90')):.3f}")
                st.metric("xG / 90 (weighted)",  f"{_safe(agg.get('weighted_xG_per90')):.3f}")
                st.metric("Assists / 90",         f"{_safe(agg.get('mean_assists_per90')):.3f}")
                st.metric("xA / 90 (weighted)",  f"{_safe(agg.get('weighted_xA_per90')):.3f}")
                st.metric("Mean FIFA Overall",    f"{_safe(agg.get('mean_overall')):.1f}")

        st.markdown("#### Position profiles")
        pc1, pc2 = st.columns(2)
        for col, label, profiles, side in [(pc1, team_a, pa, "a"), (pc2, team_b, pb, "b")]:
            with col:
                st.markdown(f"**{label}**")
                pfig = analytics.position_radar_figure(profiles)
                if pfig:
                    st.plotly_chart(pfig, width='stretch', key=f"tc_pos_{side}")


# ═══════════════════════════════════════════════════════
# Tab 2 — Player Comparison
# ═══════════════════════════════════════════════════════

with tab_players:
    def _player_map(team: str) -> Dict[str, Dict]:
        return {
            (p.get("name") or f"Player {i}"): p
            for i, p in enumerate(_raw_squads.get(team, []))
        }

    opt1, opt2, opt3 = st.columns([2, 2, 1])
    with opt3:
        pos_aware = st.checkbox(
            "Position-appropriate axes",
            help="Shows only axes relevant to each player's position",
        )
        show_wc = has_wc_stats and st.checkbox(
            "Show WC stats",
            value=has_wc_stats,
            help="Toggle between club season stats and WC tournament stats",
        )

    pc1, pc2 = st.columns(2)
    with pc1:
        pt_a  = st.selectbox("Team (A)", teams, key="pt_a")
        pm_a  = _player_map(pt_a)
        pn_a  = st.selectbox("Player A", list(pm_a.keys()), key="pn_a") if pm_a else None
        prof_a = pm_a.get(pn_a) if pn_a else None
    with pc2:
        pt_b  = st.selectbox("Team (B)", teams, key="pt_b")
        pm_b  = _player_map(pt_b)
        pn_b  = st.selectbox("Player B", list(pm_b.keys()), key="pn_b") if pm_b else None
        prof_b = pm_b.get(pn_b) if pn_b else None

    if prof_a and prof_b:
        if has_wc_stats and show_wc and prof_a.get('wc_stats') and prof_b.get('wc_stats'):
            rfig = _wc_radar(prof_a, prof_b, pn_a, pn_b, all_flat)
        else:
            rfig = _players_radar(prof_a, prof_b, pn_a, pn_b, all_flat, pos_aware=pos_aware)

        if rfig:
            st.plotly_chart(rfig, width='stretch', key="pc_radar")

        st.markdown("#### Stats")
        df_p = _player_stats_df(prof_a, prof_b, pn_a, pn_b)
        if df_p is not None:
            st.dataframe(df_p, width='stretch')
            csv = df_p.to_csv()
            st.download_button(
                "Download stats as CSV",
                csv,
                f"{pn_a}_vs_{pn_b}.csv",
                "text/csv",
                key="dl_player_csv",
            )
    else:
        st.info("Player comparison requires a selection in both columns.")


# ═══════════════════════════════════════════════════════
# Tab 3 — Squad Explorer
# ═══════════════════════════════════════════════════════

with tab_squad:
    sel_team = st.selectbox("Team", teams, key="se_team")
    profiles = squads.get(sel_team, [])
    total    = squad_sizes.get(sel_team, len(profiles))

    if not profiles:
        st.warning(f"No player data for {sel_team} (0/{total} matched) — coverage depends on leagues included in the selection.")
    else:
        st.caption(f"{len(profiles)} / {total} players matched from Wikipedia squad list")

        opt_c1, opt_c2 = st.columns([1, 3])
        with opt_c1:
            metric = st.selectbox(
                "Metric",
                _RADAR_AXES,
                format_func=_AXIS_LABEL.get,
                key="se_metric",
            )
            top_n = st.slider("Top N players", 5, min(25, len(profiles)), 10, key="se_n")
        with opt_c2:
            bar_fig = analytics.top_players_bar_figure(profiles, metric, top_n)
            if bar_fig:
                st.plotly_chart(bar_fig, width='stretch', key="se_bar")

        sc1, sc2 = st.columns(2)
        with sc1:
            scatter = analytics.minutes_weighted_scatter(profiles)
            if scatter:
                st.plotly_chart(scatter, width='stretch', key="se_scatter")
        with sc2:
            pie = analytics.club_contribution_pie(profiles)
            if pie:
                st.plotly_chart(pie, width='stretch', key="se_pie")

        pos_fig = analytics.position_radar_figure(profiles)
        if pos_fig:
            st.markdown("#### Position profiles")
            st.plotly_chart(pos_fig, width='stretch', key="se_pos_radar")

        # CSV export of squad stats
        try:
            import pandas as _pd
            rows_export = [analytics.per90_metrics(p) for p in profiles]
            df_export = _pd.DataFrame(rows_export)
            st.download_button(
                "Download squad stats as CSV",
                df_export.to_csv(index=False),
                f"{sel_team.replace(' ', '_')}_squad_stats.csv",
                "text/csv",
                key="dl_squad_csv",
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════════════
# Tab 4 — Rankings
# ═══════════════════════════════════════════════════════

with tab_rank:
    df_r = _rankings_df(squads, squad_sizes)
    if df_r is not None:
        st.dataframe(df_r, width='stretch', height=620)
        st.download_button(
            "Download rankings as CSV",
            df_r.to_csv(),
            "wc2026_rankings.csv",
            "text/csv",
            key="dl_rankings_csv",
        )
    else:
        st.info("Install pandas for the rankings table.")

    st.markdown("#### Metric distribution across all teams")
    v_metric = st.selectbox(
        "Metric",
        _RADAR_AXES,
        format_func=_AXIS_LABEL.get,
        key="viol_metric",
    )
    vfig = analytics.metric_violin_figure(squads, v_metric)
    if vfig:
        st.plotly_chart(vfig, width='stretch', key="rank_violin")


# ═══════════════════════════════════════════════════════
# Tab 5 — Group Stage
# ═══════════════════════════════════════════════════════

with tab_groups:
    if "groups" not in st.session_state:
        groups_url = st.text_input(
            "Wikipedia WC2026 main page URL",
            value=WC2026_MAIN_URL,
            key="groups_url",
        )
        if st.button("Load Groups from Wikipedia", key="load_groups"):
            with st.spinner("Parsing group tables from Wikipedia…"):
                try:
                    grps = fetch_groups_from_wikipedia(groups_url)
                    if grps:
                        st.session_state.groups = grps
                        st.rerun()
                    else:
                        st.error(
                            "No group tables found — Wikipedia page structure may have changed "
                            "or this URL may lack group heading markup."
                        )
                except Exception as exc:
                    st.error(f"Failed to load groups: {exc}")
    else:
        groups: Dict[str, List[str]] = st.session_state.groups

        if st.button("Reload groups", key="reload_groups"):
            del st.session_state.groups
            st.rerun()

        # Normalise team names to match what's in squads
        def _match_group_team(name: str) -> Optional[str]:
            """Find the squads key that best matches a Wikipedia group team name."""
            name_lower = name.lower().strip()
            for t in squads:
                if t.lower().strip() == name_lower:
                    return t
            # Partial match fallback
            for t in squads:
                if name_lower in t.lower() or t.lower() in name_lower:
                    return t
            return None

        for group_label, group_teams in sorted(groups.items()):
            with st.expander(group_label, expanded=True):
                rows = []
                for team_name in group_teams:
                    squad_key = _match_group_team(team_name)
                    profiles  = squads.get(squad_key, []) if squad_key else []
                    agg       = analytics.compute_team_aggregates(profiles)
                    elo       = analytics.team_elo_rating(profiles, all_teams_profiles=squads) if profiles else 1500.0
                    matched   = len(profiles)
                    total_wc  = squad_sizes.get(squad_key, 0) if squad_key else 0
                    rows.append({
                        "Team": team_name,
                        "Coverage": f"{matched}/{total_wc}" if total_wc else "no data",
                        "Strength": round(elo, 1),
                        "Goals / 90": round(_safe(agg.get("mean_goals_per90")), 3),
                        "xG / 90": round(_safe(agg.get("weighted_xG_per90")), 3),
                        "Mean Overall": round(_safe(agg.get("mean_overall")), 1),
                    })

                try:
                    import pandas as _pd
                    df_g = _pd.DataFrame(rows).sort_values("Strength", ascending=False)
                    df_g.index = range(1, len(df_g) + 1)
                    st.dataframe(df_g, width='stretch')
                except ImportError:
                    for r in rows:
                        st.write(r)


# ═══════════════════════════════════════════════════════
# Tab 6 — Matchup
# ═══════════════════════════════════════════════════════

with tab_matchup:
    st.markdown(
        "Ranks Team A's outfield players by their likely impact against Team B's defensive style. "
        "Score combines each player's attacking output with Team B's defensive vulnerability on the same axes, "
        "normalised across the full tournament."
    )

    mu_c1, mu_c2 = st.columns(2)
    with mu_c1:
        mu_team_a = st.selectbox("Team A (attackers)", teams, key="mu_a")
    with mu_c2:
        mu_team_b = st.selectbox("Team B (defensive reference)", teams,
                                  index=min(1, len(teams) - 1), key="mu_b")

    if mu_team_a == mu_team_b:
        st.warning("Choose two different teams.")
    else:
        mu_pa = squads.get(mu_team_a, [])
        mu_pb = squads.get(mu_team_b, [])

        # ── Team B defensive vulnerability ───────────────────────────────────
        mu_def_prof   = analytics.defensive_profile(mu_pb)
        mu_def_ranges = analytics.tournament_defensive_ranges(squads)
        mu_vuln       = analytics.defensive_vulnerability(mu_def_prof, mu_def_ranges)

        mu_defenders = [p for p in mu_pb if analytics._extract_position_from_profile(p) in ('GK', 'DEF')]
        if not mu_defenders:
            st.info(f"No DEF/GK found for {mu_team_b} — using full squad as defensive reference.")
            mu_defenders = mu_pb

        mu_def_overall = [
            _safe((p.get('aggregated') or {}).get('overall'))
            for p in mu_defenders
            if _safe((p.get('aggregated') or {}).get('overall')) > 0
        ]
        mean_def_overall = sum(mu_def_overall) / len(mu_def_overall) if mu_def_overall else 0.0

        st.markdown(f"#### {mu_team_b} defensive profile")
        vm1, vm2, vm3 = st.columns([3, 1, 1])
        with vm1:
            vfig = _vulnerability_bar(mu_vuln, mu_team_b)
            if vfig:
                st.plotly_chart(vfig, width='stretch', key="mu_vuln_bar")
        with vm2:
            st.metric("DEF/GK players", len(mu_defenders))
        with vm3:
            st.metric("Mean Overall", f"{mean_def_overall:.1f}" if mean_def_overall else "—")

        # ── Ranked player table ───────────────────────────────────────────────
        st.markdown(f"#### {mu_team_a} player impact ranking")

        mu_results = analytics.matchup_scores(mu_pa, mu_pb, squads)

        if not mu_results:
            st.warning(f"No outfield players available for {mu_team_a} at the current minutes threshold.")
        else:
            try:
                import pandas as _pd

                def _fmt(v):
                    if v is None or (isinstance(v, float) and math.isnan(v)):
                        return "—"
                    return f"{float(v):.3f}"

                table_rows = []
                for i, r in enumerate(mu_results, 1):
                    table_rows.append({
                        "Rank":          i,
                        "Name":          r['name'],
                        "Position":      r['position'],
                        "Matchup Score": round(r['matchup_score'], 3),
                        "Goals / 90":    _fmt(r['goals_per90']),
                        "xG / 90":       _fmt(r['xG_per90']),
                        "Assists / 90":  _fmt(r['assists_per90']),
                        "xA / 90":       _fmt(r['xA_per90']),
                        "Overall":       _fmt(r['overall']),
                        "Rating":        _fmt(r['rating']),
                        "Minutes":       int(r['minutes'] or 0),
                    })

                df_mu = _pd.DataFrame(table_rows).set_index("Rank")
                st.dataframe(df_mu, width='stretch', height=500)
                st.download_button(
                    "Download matchup scores as CSV",
                    df_mu.to_csv(),
                    f"{mu_team_a}_vs_{mu_team_b}_matchup.csv",
                    "text/csv",
                    key="dl_matchup_csv",
                )
            except ImportError:
                for r in mu_results:
                    st.write(r)

            # ── Optional radar overlay ────────────────────────────────────────
            if st.checkbox("Show top attacker vs Team B defence radar", key="mu_show_radar"):
                top = mu_results[0]
                top_profile = next(
                    (p for p in mu_pa if p.get('name') == top['name']), None
                )
                if top_profile:
                    # Normalise top player against all tournament players
                    p_ranges = _axis_ranges(all_flat, _RADAR_AXES)
                    top_row   = analytics.per90_metrics(top_profile)
                    top_vals  = [_norm(_safe(top_row.get(a)), *p_ranges[a]) for a in _RADAR_AXES]

                    # Normalise Team B defensive profile against tournament DEF ranges
                    def_vals = [_norm(mu_def_prof.get(a, 0.0), *mu_def_ranges[a]) for a in _RADAR_AXES]

                    rfig = _build_radar(
                        [(top['name'], top_vals), (f"{mu_team_b} Defence", def_vals)],
                        _RADAR_AXES,
                        f"{top['name']} vs {mu_team_b} Defence — normalised",
                    )
                    if rfig:
                        st.plotly_chart(rfig, width='stretch', key="mu_top_radar")
                    st.caption(
                        f"Player values normalised against all tournament players. "
                        f"{mu_team_b} defence values normalised against tournament DEF/GK field."
                    )
