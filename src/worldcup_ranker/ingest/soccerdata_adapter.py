"""Adapter that uses the `soccerdata` PyPI package to fetch data from multiple sources."""
from typing import List, Dict, Any

from worldcup_ranker.models import Player
from worldcup_ranker.normaliser import normalise_league


def _import_provider(names: List[str]):
    for name in names:
        try:
            components = name.split('.')
            mod = __import__('.'.join(components[:-1]) or components[0], fromlist=[components[-1]])
            return getattr(mod, components[-1]) if hasattr(mod, components[-1]) else mod
        except Exception:
            continue
    return None


def _ensure_package():
    try:
        import soccerdata  # type: ignore
        return soccerdata
    except Exception as e:
        raise ImportError("The `soccerdata` package is required for this adapter. Install it with `pip install soccerdata`.") from e


def fetch_fbref_player_stats(season: str, competition: str) -> List[Dict[str, Any]]:
    _ensure_package()
    Provider = _import_provider(["soccerdata.fbref.FBref", "soccerdata.providers.FBref", "soccerdata.fbref"])
    if Provider is None:
        raise RuntimeError("FBref provider not found in soccerdata. Verify your soccerdata version and provider names.")

    try:
        if callable(Provider):
            p = Provider(season=season)
        else:
            p = Provider
        rows = None
        if hasattr(p, 'player_stats'):
            rows = p.player_stats(competition)
        elif hasattr(p, 'get_player_stats'):
            rows = p.get_player_stats(competition)
        else:
            rows = getattr(p, 'data', None)

        if rows is None:
            raise RuntimeError("Unable to fetch FBref data from provider; no known method returned data.")

        try:
            import pandas as pd

            if isinstance(rows, pd.DataFrame):
                records = rows.to_dict(orient='records')
            else:
                records = list(rows)
        except Exception:
            records = list(rows)

        out: List[Dict[str, Any]] = []
        for r in records:
            name = r.get('player') or r.get('name')
            club = r.get('squad') or r.get('club') or r.get('team')
            league = r.get('competition') or ''
            out.append({
                'name': name,
                'club': club,
                'league': normalise_league(league),
                'minutes': r.get('minutes') or r.get('min') or 0,
                'matches': r.get('appearances') or r.get('apps') or 0,
                'goals': r.get('goals') or 0,
                'assists': r.get('assists') or 0,
                'raw': r,
            })
        return out
    except Exception as e:
        raise RuntimeError(f"Error fetching FBref data: {e}") from e


def fetch_understat_xg(season: str, competition: str) -> List[Dict[str, Any]]:
    _ensure_package()
    Provider = _import_provider(["soccerdata.understat.Understat", "soccerdata.understat"])
    if Provider is None:
        raise RuntimeError("Understat provider not found in soccerdata.")

    try:
        p = Provider(season=season) if callable(Provider) else Provider
        rows = None
        if hasattr(p, 'player_stats'):
            rows = p.player_stats(competition)
        elif hasattr(p, 'xg_stats'):
            rows = p.xg_stats(competition)
        else:
            rows = getattr(p, 'data', None)

        try:
            import pandas as pd
            if isinstance(rows, pd.DataFrame):
                records = rows.to_dict(orient='records')
            else:
                records = list(rows)
        except Exception:
            records = list(rows)

        out = []
        for r in records:
            out.append({
                'name': r.get('player') or r.get('name'),
                'xG': r.get('xG') or r.get('xg') or 0.0,
                'xA': r.get('xA') or r.get('xa') or 0.0,
                'minutes': r.get('minutes') or 0,
                'raw': r,
            })
        return out
    except Exception as e:
        raise RuntimeError(f"Error fetching Understat data: {e}") from e


def fetch_sofifa_attributes(version: str = 'latest') -> List[Dict[str, Any]]:
    _ensure_package()
    Provider = _import_provider(["soccerdata.sofifa.SoFIFA", "soccerdata.sofifa"])
    if Provider is None:
        raise RuntimeError("SoFIFA provider not found in soccerdata.")

    try:
        p = Provider(version=version) if callable(Provider) else Provider
        rows = None
        if hasattr(p, 'player_attributes'):
            rows = p.player_attributes()
        else:
            rows = getattr(p, 'data', None)

        try:
            import pandas as pd
            if isinstance(rows, pd.DataFrame):
                records = rows.to_dict(orient='records')
            else:
                records = list(rows)
        except Exception:
            records = list(rows)

        out = []
        for r in records:
            out.append({
                'name': r.get('short_name') or r.get('name'),
                'overall': r.get('overall') or r.get('ovr'),
                'potential': r.get('potential'),
                'attributes': r,
            })
        return out
    except Exception as e:
        raise RuntimeError(f"Error fetching SoFIFA data: {e}") from e


def fetch_sofascore_season_updates(competition: str, season: str) -> List[Dict[str, Any]]:
    _ensure_package()
    Provider = _import_provider(["soccerdata.sofascore.SofaScore", "soccerdata.sofascore"])
    if Provider is None:
        raise RuntimeError("Sofascore provider not found in soccerdata.")

    try:
        p = Provider(season=season) if callable(Provider) else Provider
        rows = None
        if hasattr(p, 'player_stats'):
            rows = p.player_stats(competition)
        else:
            rows = getattr(p, 'data', None)

        try:
            import pandas as pd
            if isinstance(rows, pd.DataFrame):
                records = rows.to_dict(orient='records')
            else:
                records = list(rows)
        except Exception:
            records = list(rows)

        out = []
        for r in records:
            out.append({
                'name': r.get('player') or r.get('name'),
                'rating': r.get('rating') or r.get('sofascore') or None,
                'minutes': r.get('minutes') or 0,
                'raw': r,
            })
        return out
    except Exception as e:
        raise RuntimeError(f"Error fetching Sofascore data: {e}") from e


def fetch_tournament_stats(tournament: str = "FIFA World Cup", season: str = "2026") -> List[Dict[str, Any]]:
    """Fetch player stats for the WC tournament itself via FBref.

    Uses the same FBref adapter but pointed at the WC competition rather than a
    domestic league.  Falls back gracefully if the competition is not yet available.
    """
    _ensure_package()
    Provider = _import_provider(["soccerdata.fbref.FBref", "soccerdata.providers.FBref", "soccerdata.fbref"])
    if Provider is None:
        raise RuntimeError("FBref provider not found in soccerdata.")

    try:
        p = Provider(season=season) if callable(Provider) else Provider
        rows = None
        for method in ('player_stats', 'get_player_stats'):
            if hasattr(p, method):
                rows = getattr(p, method)(tournament)
                break
        if rows is None:
            rows = getattr(p, 'data', None)
        if rows is None:
            raise RuntimeError("FBref returned no data for the tournament.")

        try:
            import pandas as pd
            if isinstance(rows, pd.DataFrame):
                records = rows.to_dict(orient='records')
            else:
                records = list(rows)
        except Exception:
            records = list(rows)

        out: List[Dict[str, Any]] = []
        for r in records:
            name = r.get('player') or r.get('name')
            out.append({
                'name': name,
                'country': r.get('nation') or r.get('country') or r.get('nationality'),
                'minutes': r.get('minutes') or r.get('min') or 0,
                'matches': r.get('appearances') or r.get('apps') or 0,
                'goals': r.get('goals') or 0,
                'assists': r.get('assists') or 0,
                'xG': r.get('xG') or r.get('xg') or 0.0,
                'xA': r.get('xA') or r.get('xa') or 0.0,
                'raw': r,
            })
        return out
    except Exception as e:
        raise RuntimeError(f"Error fetching tournament stats: {e}") from e


def map_to_player(record: Dict[str, Any]) -> Player:
    name = record.get('name')
    club = record.get('club') or record.get('team') or ''
    league = normalise_league(record.get('league') or '')
    return Player(name=name or 'UNKNOWN', club=club or '', league=league)
