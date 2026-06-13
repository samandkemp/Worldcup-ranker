from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from worldcup_ranker.db import SimpleJSONDB


class Storage:
    def __init__(self, base_path: Union[str, Path]):
        base = Path(base_path)
        base.mkdir(parents=True, exist_ok=True)
        self.players = SimpleJSONDB(str(base / 'players.json'))
        self.teams = SimpleJSONDB(str(base / 'teams.json'))
        self.raw = SimpleJSONDB(str(base / 'raw_sources.json'))
        self.squads_cache_db = SimpleJSONDB(str(base / 'squads_cache.json'))

    def load_players(self) -> Any:
        return self.players.load()

    def save_players(self, data: Any) -> None:
        self.players.save(data)

    def load_raw(self) -> Any:
        return self.raw.load()

    def save_raw(self, data: Any) -> None:
        self.raw.save(data)

    def save_squads_cache(
        self,
        squads: Dict[str, List[Dict]],
        squad_sizes: Dict[str, int],
        season: str,
        leagues: List[str],
        wiki_url: str,
    ) -> None:
        slim = {country: [_slim_profile(p) for p in profiles] for country, profiles in squads.items()}
        self.squads_cache_db.save({
            'squads': slim,
            'squad_sizes': squad_sizes,
            'fetched_at': datetime.now().isoformat(timespec='seconds'),
            'season': season,
            'leagues': leagues,
            'wiki_url': wiki_url,
        })

    def load_squads_cache(self) -> Optional[Dict]:
        try:
            data = self.squads_cache_db.load()
            if data and data.get('squads'):
                return data
        except Exception:
            pass
        return None


def _slim_profile(profile: Dict) -> Dict:
    """Return a cache-safe profile: aggregated stats kept, raw records stripped to
    just club and position so club_contribution_pie and position detection still work."""
    raw_slim = []
    for item in profile.get('raw', []):
        rec = item.get('record', {})
        raw_slim.append({
            'provider': item.get('provider'),
            'record': {
                'club': rec.get('club') or rec.get('team') or rec.get('squad'),
                'position': rec.get('position') or rec.get('pos') or rec.get('role'),
            },
        })
    result = {
        'name': profile.get('name'),
        'aliases': profile.get('aliases', []),
        'minutes': profile.get('minutes', 0),
        'matches': profile.get('matches', 0),
        'aggregated': profile.get('aggregated', {}),
        'raw': raw_slim,
    }
    if 'wc_stats' in profile:
        result['wc_stats'] = profile['wc_stats']
    return result
