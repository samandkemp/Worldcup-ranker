"""Adapter for the `soccerdata` 1.9.x PyPI package."""
from typing import List, Dict, Any

from worldcup_ranker.models import Player
from worldcup_ranker.normaliser import normalise_league


def _ensure_soccerdata():
    try:
        import soccerdata
        return soccerdata
    except ImportError as e:
        raise ImportError(
            "The `soccerdata` package is required. Install with `pip install soccerdata`."
        ) from e


def _flatten(df):
    """Reset index and flatten MultiIndex columns to 'Group_Stat' strings."""
    df = df.reset_index()
    if df.columns.nlevels > 1:
        df.columns = [
            '_'.join(str(p) for p in col).strip('_') if isinstance(col, tuple) else col
            for col in df.columns
        ]
    return df


def _col(row: dict, *candidates):
    """Return the first non-None value found among candidate keys."""
    for k in candidates:
        v = row.get(k)
        if v is not None:
            return v
    return None


def fetch_fbref_player_stats(season: str, competition: str) -> List[Dict[str, Any]]:
    sd = _ensure_soccerdata()
    try:
        fb = sd.FBref(leagues=competition, seasons=season)
        df = fb.read_player_season_stats(stat_type="standard")
        df = _flatten(df)
    except Exception as e:
        raise RuntimeError(f"Error fetching FBref data: {e}") from e

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        r = dict(row)
        out.append({
            'name':    _col(r, 'player_', 'player'),
            'club':    _col(r, 'team_', 'team', 'squad'),
            'league':  normalise_league(str(_col(r, 'league_', 'league') or '')),
            'position': _col(r, 'pos_', 'pos', 'position'),
            'minutes': _col(r, 'Playing Time_Min', 'Min', 'minutes', 'min') or 0,
            'matches': _col(r, 'Playing Time_MP', 'MP', 'matches', 'apps') or 0,
            'goals':   _col(r, 'Performance_Gls', 'Gls', 'goals') or 0,
            'assists': _col(r, 'Performance_Ast', 'Ast', 'assists') or 0,
            'raw': r,
        })
    return out


def fetch_understat_xg(season: str, competition: str) -> List[Dict[str, Any]]:
    sd = _ensure_soccerdata()
    try:
        us = sd.Understat(leagues=competition, seasons=season)
        df = us.read_player_season_stats()
        df = _flatten(df)
    except Exception as e:
        raise RuntimeError(f"Error fetching Understat data: {e}") from e

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        r = dict(row)
        out.append({
            'name':    _col(r, 'player_', 'player', 'name'),
            'xG':      _col(r, 'xG', 'xg') or 0.0,
            'xA':      _col(r, 'xA', 'xa') or 0.0,
            'minutes': _col(r, 'minutes', 'min', 'Playing Time_Min') or 0,
            'raw': r,
        })
    return out


def fetch_sofifa_attributes(version: str = 'latest') -> List[Dict[str, Any]]:
    sd = _ensure_soccerdata()
    try:
        sf = sd.SoFIFA()
        df = sf.read_player_ratings()
        df = _flatten(df)
    except Exception as e:
        raise RuntimeError(f"Error fetching SoFIFA data: {e}") from e

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        r = dict(row)
        out.append({
            'name':      _col(r, 'player_', 'player', 'short_name', 'name'),
            'overall':   _col(r, 'overall', 'ovr'),
            'potential': _col(r, 'potential'),
            'attributes': r,
        })
    return out


def fetch_sofascore_season_updates(competition: str, season: str) -> List[Dict[str, Any]]:
    # soccerdata 1.9.x Sofascore does not expose player stats — return empty.
    raise RuntimeError("Sofascore player stats are not available in soccerdata 1.9.x.")


def fetch_tournament_stats(tournament: str = "INT-World Cup", season: str = "2526") -> List[Dict[str, Any]]:
    """Fetch WC tournament player stats via FBref."""
    sd = _ensure_soccerdata()
    try:
        fb = sd.FBref(leagues=tournament, seasons=season)
        df = fb.read_player_season_stats(stat_type="standard")
        df = _flatten(df)
    except Exception as e:
        raise RuntimeError(f"Error fetching tournament stats: {e}") from e

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        r = dict(row)
        out.append({
            'name':    _col(r, 'player_', 'player'),
            'country': _col(r, 'nation_', 'nation', 'nationality', 'country'),
            'minutes': _col(r, 'Playing Time_Min', 'Min', 'minutes') or 0,
            'matches': _col(r, 'Playing Time_MP', 'MP', 'matches') or 0,
            'goals':   _col(r, 'Performance_Gls', 'Gls', 'goals') or 0,
            'assists': _col(r, 'Performance_Ast', 'Ast', 'assists') or 0,
            'xG':      _col(r, 'Expected_xG', 'xG', 'xg') or 0.0,
            'xA':      _col(r, 'Expected_xAG', 'xA', 'xa') or 0.0,
            'raw': r,
        })
    return out


def map_to_player(record: Dict[str, Any]) -> Player:
    name = record.get('name')
    club = record.get('club') or record.get('team') or ''
    league = normalise_league(record.get('league') or '')
    return Player(name=name or 'UNKNOWN', club=club or '', league=league)
