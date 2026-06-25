from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from worldcup_ranker.ingest import soccerdata_adapter
from worldcup_ranker.merge import merge_provider_records
from worldcup_ranker.storage import Storage
from worldcup_ranker.ingest import wiki_adapter
from worldcup_ranker.match_utils import normalise_name, fuzzy_match


def build_canonical_players_from_providers(
    providers: Dict[str, List[Dict[str, Any]]],
    storage_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    canonical = merge_provider_records(providers, primary='fbref')
    if storage_path:
        s = Storage(storage_path)
        s.save_players(canonical)
    return canonical


def filter_canonical_by_squads(
    canonical: List[Dict[str, Any]],
    squads: Dict[str, List[str]],
    cutoff: float = 0.85,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, int]]:
    """Match canonical player profiles against Wikipedia squad name lists.

    Returns ``(country -> profiles, country -> squad_size_from_wikipedia)``.
    The squad_size gives the total number of names on the Wikipedia page so
    callers can compute coverage (matched / total).
    """
    squad_sizes = {country: len(names) for country, names in squads.items()}

    alias_map: Dict[str, Dict] = {}
    for prof in canonical:
        for a in prof.get('aliases', []):
            alias_map[a] = prof

    all_aliases = list(alias_map.keys())
    result: Dict[str, List[Dict[str, Any]]] = {}

    for country, names in squads.items():
        matched = []
        for n in names:
            if n in alias_map:
                matched.append(alias_map[n])
                continue
            candidates = fuzzy_match(n, all_aliases, cutoff=cutoff)
            if candidates:
                matched.append(alias_map[candidates[0]])
        result[country] = matched

    return result, squad_sizes


def fetch_for_leagues(
    leagues: List[str],
    season: str,
    tournament_wiki_url: str,
    storage_path: Optional[str] = None,
    force_refresh: bool = False,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, int], List[str]]:
    """Fetch player stats across multiple leagues, merge, and filter to WC squads.

    Returns ``(country -> profiles, country -> squad_size, warnings)``.
    The squad_size dict records how many players each country had listed on
    Wikipedia so the UI can show coverage (e.g. "22 / 26 matched").
    Results are cached to ``storage_path/squads_cache.json`` for instant reload.
    """
    all_providers: Dict[str, List[Dict[str, Any]]] = {}
    all_warnings: List[str] = []

    for competition in leagues:
        providers = fetch_providers_for_competition(
            season=season,
            competition=competition,
            storage_path=storage_path,
            force_refresh=force_refresh,
        )
        for w in providers.get('_warnings', []):
            all_warnings.append(f"[{competition}] {w}")
        for prov, recs in providers.items():
            if prov.startswith('_'):
                continue
            all_providers.setdefault(prov, []).extend(recs)

    canonical = build_canonical_players_from_providers(all_providers)
    squads_raw = wiki_adapter.fetch_squads_from_wikipedia(tournament_wiki_url)
    filtered, squad_sizes = filter_canonical_by_squads(canonical, squads_raw)

    if storage_path:
        try:
            storage = Storage(storage_path)
            storage.save_squads_cache(filtered, squad_sizes, season, leagues, tournament_wiki_url)
        except Exception as e:
            all_warnings.append(f"Cache save failed: {e}")

    return filtered, squad_sizes, all_warnings


def enrich_with_tournament_stats(
    squads: Dict[str, List[Dict[str, Any]]],
    tournament: str = "INT-World Cup",
    season: str = "2526",
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
    """Fetch WC match stats from FBref and attach them to matching player profiles.

    Adds a ``wc_stats`` dict to each matched profile with keys:
    minutes, matches, goals, assists, xG, xA.

    Returns ``(enriched_squads, warnings)``.
    """
    warnings: List[str] = []

    try:
        wc_records = soccerdata_adapter.fetch_tournament_stats(tournament=tournament, season=season)
    except Exception as e:
        return squads, [f"Could not fetch WC match stats: {e}"]

    if not wc_records:
        return squads, ["WC match stats returned empty — the competition may not be available yet on FBref."]

    wc_index: Dict[str, Dict] = {}
    for rec in wc_records:
        n = normalise_name(rec.get('name') or '')
        if n:
            wc_index[n] = rec

    wc_names = list(wc_index.keys())
    enriched = 0

    for profiles in squads.values():
        for profile in profiles:
            matched_rec = None
            for alias in profile.get('aliases', [normalise_name(profile.get('name') or '')]):
                if alias in wc_index:
                    matched_rec = wc_index[alias]
                    break
            if not matched_rec:
                candidates = fuzzy_match(
                    normalise_name(profile.get('name') or ''),
                    wc_names,
                    cutoff=0.88,
                )
                if candidates:
                    matched_rec = wc_index[candidates[0]]

            if matched_rec:
                profile['wc_stats'] = {
                    'minutes': int(matched_rec.get('minutes') or 0),
                    'matches': int(matched_rec.get('matches') or 0),
                    'goals': float(matched_rec.get('goals') or 0),
                    'assists': float(matched_rec.get('assists') or 0),
                    'xG': float(matched_rec.get('xG') or 0.0),
                    'xA': float(matched_rec.get('xA') or 0.0),
                }
                enriched += 1

    if enriched == 0:
        warnings.append(
            f"No players could be matched to WC stats ({tournament} {season}). "
            "The competition may not yet be available on FBref."
        )
    else:
        warnings.append(f"WC stats attached to {enriched} players.")

    return squads, warnings


def fetch_and_filter(
    season: str,
    competition: str,
    tournament_wiki_url: str,
    storage_path: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    providers = fetch_providers_for_competition(season=season, competition=competition)
    canonical = build_canonical_players_from_providers(providers, storage_path=storage_path)
    squads_raw = wiki_adapter.fetch_squads_from_wikipedia(tournament_wiki_url)
    filtered, _ = filter_canonical_by_squads(canonical, squads_raw)
    return filtered


def fetch_providers_for_competition(
    season: str,
    competition: str,
    storage_path: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    providers: Dict[str, List[Dict[str, Any]]] = {}
    warnings: List[str] = []

    cache_key = f"{season}__{competition}"
    storage = None
    cached = None
    if storage_path:
        storage = Storage(storage_path)
        try:
            raw = storage.load_raw() or {}
            cached = raw.get(cache_key)
        except Exception:
            cached = None

    if cached and not force_refresh:
        return cached

    try:
        providers['fbref'] = soccerdata_adapter.fetch_fbref_player_stats(season=season, competition=competition)
    except Exception as e:
        warnings.append(f"fbref: {e}")

    try:
        providers['understat'] = soccerdata_adapter.fetch_understat_xg(season=season, competition=competition)
    except Exception as e:
        warnings.append(f"understat: {e}")

    try:
        providers['sofifa'] = soccerdata_adapter.fetch_sofifa_attributes()
    except Exception as e:
        warnings.append(f"sofifa: {e}")

    try:
        providers['sofascore'] = soccerdata_adapter.fetch_sofascore_season_updates(competition=competition, season=season)
    except Exception as e:
        warnings.append(f"sofascore: {e}")

    providers['_warnings'] = warnings

    if storage is not None:
        try:
            raw = storage.load_raw() or {}
        except Exception:
            raw = {}
        raw[cache_key] = providers
        try:
            storage.save_raw(raw)
        except Exception:
            pass

    return providers
