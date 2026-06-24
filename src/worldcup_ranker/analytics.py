import math
from typing import List, Dict, Any, Tuple, Optional

# Lazy imports: prefer pandas/plotly when available but keep pure-Python fallbacks
try:
    import pandas as pd
except Exception:
    pd = None

try:
    import plotly.express as px
except Exception:
    px = None


def _agg_from_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    return profile.get('aggregated') or {}


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return math.nan


def per90_metrics(profile: Dict[str, Any]) -> Dict[str, float]:
    agg = _agg_from_profile(profile)
    minutes = int(agg.get('minutes') or 0)
    minutes = max(minutes, 0)
    def p90(val):
        try:
            valf = float(val)
        except Exception:
            return math.nan
        return (valf / minutes * 90.0) if minutes > 0 else math.nan

    return {
        'name': profile.get('name'),
        'minutes': minutes,
        'matches': int(agg.get('matches') or 0),
        'goals': _safe_float(agg.get('goals')),
        'assists': _safe_float(agg.get('assists')),
        'xG': _safe_float(agg.get('xG')),
        'xA': _safe_float(agg.get('xA')),
        'overall': _safe_float(agg.get('overall')),
        'rating': _safe_float(agg.get('rating')),
        'goals_per90': p90(agg.get('goals') or 0),
        'assists_per90': p90(agg.get('assists') or 0),
        'xG_per90': p90(agg.get('xG') or 0.0),
        'xA_per90': p90(agg.get('xA') or 0.0),
    }


def compute_team_aggregates(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute team-level aggregates (minutes-weighted where appropriate).

    If `pandas` is available we use it; otherwise fall back to pure-Python.
    """
    rows = [per90_metrics(p) for p in profiles]
    if not rows:
        return {}

    if pd is not None:
        df = pd.DataFrame(rows)
        total_minutes = int(df['minutes'].sum(skipna=True))

        def weighted_mean(col):
            try:
                return float((df[col] * df['minutes']).sum() / max(1, df['minutes'].sum()))
            except Exception:
                return math.nan

        team = {
            'players': len(df),
            'total_minutes': int(total_minutes),
            'mean_goals_per90': float(df['goals_per90'].mean(skipna=True)),
            'mean_assists_per90': float(df['assists_per90'].mean(skipna=True)),
            'weighted_xG_per90': weighted_mean('xG_per90'),
            'weighted_xA_per90': weighted_mean('xA_per90'),
            'mean_overall': float(df['overall'].mean(skipna=True)) if 'overall' in df else math.nan,
            'mean_rating': float(df['rating'].mean(skipna=True)) if 'rating' in df else math.nan,
        }
        return team

    # pure-Python fallback
    total_minutes = sum(r.get('minutes', 0) for r in rows)

    def mean_py(key):
        vals = [v for v in (r.get(key) for r in rows) if isinstance(v, (int, float)) and not math.isnan(v)]
        return float(sum(vals) / len(vals)) if vals else math.nan

    def weighted_mean_py(key):
        try:
            num = sum((r.get(key) or 0) * (r.get('minutes') or 0) for r in rows)
            denom = max(1, sum(r.get('minutes') or 0 for r in rows))
            return float(num) / denom
        except Exception:
            return math.nan

    team = {
        'players': len(rows),
        'total_minutes': int(total_minutes),
        'mean_goals_per90': mean_py('goals_per90'),
        'mean_assists_per90': mean_py('assists_per90'),
        'weighted_xG_per90': weighted_mean_py('xG_per90'),
        'weighted_xA_per90': weighted_mean_py('xA_per90'),
        'mean_overall': mean_py('overall'),
        'mean_rating': mean_py('rating'),
    }
    return team


def top_n_players_by_metric(profiles: List[Dict[str, Any]], metric: str, n: int = 10):
    rows = [per90_metrics(p) for p in profiles]
    if not rows:
        return []
    try:
        return sorted(rows, key=lambda r: (r.get(metric) or -math.inf), reverse=True)[:n]
    except Exception:
        return rows[:n]


def top_players_bar_figure(profiles: List[Dict[str, Any]], metric: str, n: int = 10):
    if px is None:
        return None
    rows = top_n_players_by_metric(profiles, metric, n)
    if not rows:
        return None
    try:
        import pandas as _pd
        df = _pd.DataFrame(rows)
        fig = px.bar(df, x='name', y=metric, hover_data=['minutes', 'matches'], title=f'Top {n} players by {metric}')
        fig.update_layout(xaxis_tickangle=-45)
        return fig
    except Exception:
        return None


def team_radar_figure(profiles: List[Dict[str, Any]], use_top_n: int = 11):
    rows = [per90_metrics(p) for p in profiles]
    if not rows or px is None:
        return None
    # top-N by minutes, averaged across radar axes
    rows_sorted = sorted(rows, key=lambda r: r.get('minutes', 0), reverse=True)[:use_top_n]
    axes = ['goals_per90','xG_per90','assists_per90','xA_per90','overall','rating']
    vals = []
    for a in axes:
        vals.append(float(sum((r.get(a) or 0.0) for r in rows_sorted) / max(1, len(rows_sorted))))
    fig = px.line_polar(r=vals, theta=axes, line_close=True, title='Team profile (averaged top players)')
    return fig


def minutes_weighted_scatter(profiles: List[Dict[str, Any]]):
    rows = [per90_metrics(p) for p in profiles]
    if not rows or px is None:
        return None
    try:
        import pandas as _pd
        df = _pd.DataFrame(rows)
        if 'xG_per90' not in df or 'xA_per90' not in df:
            return None
        fig = px.scatter(df, x='xG_per90', y='xA_per90', size='minutes', hover_name='name', title='xG vs xA per90 (size=minutes)')
        return fig
    except Exception:
        return None


def club_contribution_pie(profiles: List[Dict[str, Any]]):
    # aggregate minutes by club from raw source records
    clubs = {}
    for p in profiles:
        name = p.get('name')
        club = ''
        for item in p.get('raw', []):
            rec = item.get('record', {})
            club = rec.get('club') or rec.get('team') or rec.get('squad') or club
        minutes = 0
        try:
            minutes = int((p.get('aggregated') or {}).get('minutes') or 0)
        except Exception:
            minutes = 0
        clubs.setdefault(club or 'Unknown', 0)
        clubs[club or 'Unknown'] += minutes
    if pd is None or px is None or not clubs:
        return None
    df = pd.DataFrame([{'club': k, 'minutes': v} for k, v in clubs.items()])
    if df.empty:
        return None
    fig = px.pie(df, values='minutes', names='club', title='Club minutes contribution')
    return fig


def metric_violin_figure(all_country_profiles: Dict[str, List[Dict[str, Any]]], metric: str):
    # all_country_profiles: country -> profiles
    if px is None:
        return None
    rows = []
    for country, profiles in (all_country_profiles or {}).items():
        for p in profiles:
            r = per90_metrics(p)
            rows.append({'country': country, 'name': r.get('name'), metric: r.get(metric)})
    try:
        import pandas as _pd
        df = _pd.DataFrame(rows)
        if metric not in df.columns:
            return None
        fig = px.violin(df, x='country', y=metric, box=True, points='outliers', title=f'Distribution of {metric} across countries')
        fig.update_layout(xaxis_tickangle=-45)
        return fig
    except Exception:
        return None


def _extract_position_from_profile(profile: Dict[str, Any]) -> str:
    # raw records use varying field names for position across providers
    pos = None
    for item in profile.get('raw', []):
        rec = item.get('record') or {}
        for key in ('position', 'pos', 'role'):
            if key in rec and rec.get(key):
                pos = str(rec.get(key))
                break
        if pos:
            break
    if not pos:
        # try aggregated or top-level
        pos = profile.get('position') or (profile.get('aggregated') or {}).get('position')
    if not pos:
        return 'Unknown'
    p = str(pos).lower()
    # normalises to GK / DEF / MID / FWD buckets
    if 'goal' in p or p.startswith('gk'):
        return 'GK'
    if 'def' in p or 'back' in p or p.startswith('cb') or p.startswith('lb') or p.startswith('rb'):
        return 'DEF'
    if 'mid' in p or 'centre' in p or 'cm' in p or 'dm' in p or 'am' in p:
        return 'MID'
    if 'att' in p or 'fw' in p or 'forw' in p or 'strik' in p or 'wing' in p or p.startswith('st'):
        return 'FWD'
    return 'Unknown'


def position_aggregates(profiles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return aggregates per broad position group (GK/DEF/MID/FWD)."""
    buckets: Dict[str, Dict[str, Any]] = {}
    rows = [per90_metrics(p) for p in profiles]
    if not rows:
        return {}
    positions = [_extract_position_from_profile(p) for p in profiles]
    # group rows by position
    group_map: Dict[str, List[Dict[str, Any]]] = {}
    for pos, row in zip(positions, rows):
        group_map.setdefault(pos, []).append(row)

    for grp, items in group_map.items():
        def avg(k):
            vals = [v for v in (it.get(k) for it in items) if isinstance(v, (int, float)) and not math.isnan(v)]
            return float(sum(vals) / len(vals)) if vals else 0.0

        buckets[grp] = {
            'count': int(len(items)),
            'mean_goals_per90': avg('goals_per90'),
            'mean_assists_per90': avg('assists_per90'),
            'mean_xG_per90': avg('xG_per90'),
            'mean_xA_per90': avg('xA_per90'),
            'mean_overall': float(sum((it.get('overall') or 0) for it in items) / len(items)) if items else math.nan,
        }
    return buckets


def team_elo_rating(profiles: List[Dict[str, Any]], all_teams_profiles: Dict[str, List[Dict[str, Any]]] = None, base: float = 1500.0, scale: float = 100.0) -> float:
    """Compute an ELO-style team rating derived from player values.

    - If `all_teams_profiles` is provided (mapping country->profiles), use it to compute a global baseline.
    - Player value preference: use `overall` where available, otherwise a linear combination of attacking per90 metrics.
    - Team value is minutes-weighted average of player values.
    - ELO = base + (team_value - global_mean) * scale
    """
    def player_value(row):
        # prefer overall
        ov = row.get('overall')
        if ov and not math.isnan(ov):
            return float(ov)
        # fallback composite
        return float((row.get('goals_per90') or 0.0) * 6.0 + (row.get('assists_per90') or 0.0) * 4.0 + (row.get('xG_per90') or 0.0) * 2.0)

    rows = [per90_metrics(p) for p in profiles]
    if not rows:
        return base
    pvals = [player_value(r) for r in rows]
    minutes = [r.get('minutes', 0) or 0 for r in rows]
    total_minutes = sum(minutes)
    if total_minutes > 0:
        team_value = sum(p * m for p, m in zip(pvals, minutes)) / total_minutes
    else:
        team_value = sum(pvals) / len(pvals)

    # compute global mean
    global_mean = team_value
    if all_teams_profiles:
        vals = []
        for profs in all_teams_profiles.values():
            rows2 = [per90_metrics(p) for p in profs]
            if not rows2:
                continue
            pvals2 = [player_value(r) for r in rows2]
            mins2 = [r.get('minutes', 0) or 0 for r in rows2]
            if sum(mins2) > 0:
                vals.append(sum(p * m for p, m in zip(pvals2, mins2)) / sum(mins2))
            else:
                vals.append(sum(pvals2) / len(pvals2))
        if vals:
            global_mean = sum(vals) / len(vals)

    elo = float(base + (team_value - global_mean) * scale)
    return elo


def position_radar_figure(profiles: List[Dict[str, Any]]):
    buckets = position_aggregates(profiles)
    if not buckets or pd is None or px is None:
        return None
    axes = ['mean_goals_per90','mean_xG_per90','mean_assists_per90','mean_xA_per90','mean_overall']
    fig = None
    # build a small dataframe for plotting multiple traces
    rows = []
    for grp, vals in buckets.items():
        row = {'position': grp}
        for a in axes:
            row[a] = vals.get(a) or 0.0
        rows.append(row)
    df = pd.DataFrame(rows)
    # Plot using line_polar with one trace per position by melting
    df_m = df.melt(id_vars=['position'], value_vars=axes, var_name='axis', value_name='value')
    fig = px.line_polar(df_m, r='value', theta='axis', color='position', line_close=True, title='Position profiles')
    return fig


# ── Matchup scoring ───────────────────────────────────────────────────────────

_MATCHUP_AXES = ["goals_per90", "xG_per90", "assists_per90", "xA_per90", "overall", "rating"]

DEFAULT_MATCHUP_WEIGHTS: Dict[str, float] = {
    "goals_per90":   2.0,
    "xG_per90":      2.0,
    "assists_per90": 1.5,
    "xA_per90":      1.5,
    "overall":       1.0,
    "rating":        1.0,
}


def _norm_a(val: float, mn: float, mx: float) -> float:
    """Clamp-normalise val to [0, 1] within [mn, mx]."""
    return max(0.0, min(1.0, (val - mn) / (mx - mn)))


def defensive_profile(
    profiles: List[Dict[str, Any]],
    axes: Optional[List[str]] = None,
) -> Dict[str, float]:
    """Average per90 values for a team's DEF and GK players on each axis.
    Falls back to the full squad when no DEF/GK players are present in the data.
    """
    if axes is None:
        axes = _MATCHUP_AXES
    defenders = [p for p in profiles if _extract_position_from_profile(p) in ('GK', 'DEF')]
    pool = defenders if defenders else profiles
    result: Dict[str, float] = {}
    for a in axes:
        vals = []
        for p in pool:
            v = per90_metrics(p).get(a)
            if v is not None and isinstance(v, (int, float)) and not math.isnan(float(v)):
                vals.append(float(v))
        result[a] = float(sum(vals) / len(vals)) if vals else 0.0
    return result


def tournament_defensive_ranges(
    squads: Dict[str, List[Dict[str, Any]]],
    axes: Optional[List[str]] = None,
) -> Dict[str, Tuple[float, float]]:
    """Min/max of DEF+GK per90 values across all teams for each axis.
    Used to normalise a team's defensive profile against the tournament field.
    """
    if axes is None:
        axes = _MATCHUP_AXES
    pooled: Dict[str, List[float]] = {a: [] for a in axes}
    for profiles in squads.values():
        defenders = [p for p in profiles if _extract_position_from_profile(p) in ('GK', 'DEF')]
        pool = defenders if defenders else profiles
        for p in pool:
            row = per90_metrics(p)
            for a in axes:
                v = row.get(a)
                if v is not None and isinstance(v, (int, float)) and not math.isnan(float(v)):
                    pooled[a].append(float(v))
    ranges: Dict[str, Tuple[float, float]] = {}
    for a in axes:
        vals = pooled[a]
        if len(vals) >= 2:
            mn, mx = min(vals), max(vals)
            ranges[a] = (mn, mx if mx > mn else mn + 1e-6)
        else:
            ranges[a] = (0.0, 1.0)
    return ranges


def defensive_vulnerability(
    def_profile: Dict[str, float],
    def_ranges: Dict[str, Tuple[float, float]],
) -> Dict[str, float]:
    """Per-axis vulnerability of a defensive profile relative to tournament DEF ranges.
    Score of 1.0 means weakest defence in the tournament on that axis; 0.0 means strongest.
    Missing or NaN values default to 0.5 (neutral — neither punished nor rewarded).
    """
    result: Dict[str, float] = {}
    for a, (mn, mx) in def_ranges.items():
        v = def_profile.get(a)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            result[a] = 0.5
        else:
            result[a] = 1.0 - _norm_a(float(v), mn, mx)
    return result


def matchup_scores(
    team_a_profiles: List[Dict[str, Any]],
    team_b_profiles: List[Dict[str, Any]],
    all_squads: Dict[str, List[Dict[str, Any]]],
    weights: Optional[Dict[str, float]] = None,
    axes: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Rank Team A's outfield players by their likely impact against Team B's defence.

    Score = Σ weight[a] × norm_player_value[a] × vulnerability[a]

    Where norm_player_value is normalised against all tournament players on that axis,
    and vulnerability is Team B's defensive weakness on that axis relative to all teams.

    GK players from Team A are excluded. Returns results sorted by matchup_score descending.
    """
    if axes is None:
        axes = _MATCHUP_AXES
    if weights is None:
        weights = DEFAULT_MATCHUP_WEIGHTS

    # Set team B defensive context
    def_prof = defensive_profile(team_b_profiles, axes)
    def_ranges = tournament_defensive_ranges(all_squads, axes)
    vuln = defensive_vulnerability(def_prof, def_ranges)

    # Tournament-wide player ranges for normalising attacking output
    all_flat = [p for profiles in all_squads.values() for p in profiles]
    player_ranges: Dict[str, Tuple[float, float]] = {}
    for a in axes:
        vals = []
        for p in all_flat:
            v = per90_metrics(p).get(a)
            if v is not None and isinstance(v, (int, float)) and not math.isnan(float(v)):
                vals.append(float(v))
        if len(vals) >= 2:
            mn, mx = min(vals), max(vals)
            player_ranges[a] = (mn, mx if mx > mn else mn + 1e-6)
        else:
            player_ranges[a] = (0.0, 1.0)

    results = []
    for profile in team_a_profiles:
        if _extract_position_from_profile(profile) == 'GK':
            continue
        row = per90_metrics(profile)
        axis_contributions: Dict[str, float] = {}
        total = 0.0
        for a in axes:
            v = row.get(a)
            safe_v = float(v) if (v is not None and isinstance(v, (int, float)) and not math.isnan(float(v))) else 0.0
            norm_v = _norm_a(safe_v, *player_ranges[a])
            contribution = weights.get(a, 1.0) * norm_v * vuln.get(a, 0.5)
            axis_contributions[a] = round(contribution, 4)
            total += contribution

        results.append({
            'name':              profile.get('name'),
            'position':          _extract_position_from_profile(profile),
            'matchup_score':     round(total, 4),
            'axis_contributions': axis_contributions,
            'goals_per90':       row.get('goals_per90'),
            'xG_per90':          row.get('xG_per90'),
            'assists_per90':     row.get('assists_per90'),
            'xA_per90':          row.get('xA_per90'),
            'overall':           row.get('overall'),
            'rating':            row.get('rating'),
            'minutes':           row.get('minutes'),
            'matches':           row.get('matches'),
        })

    results.sort(key=lambda r: r['matchup_score'], reverse=True)
    return results
