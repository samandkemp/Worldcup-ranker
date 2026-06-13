import csv
from pathlib import Path
from typing import List, Dict, Optional

from worldcup_ranker.models import Player


def load_players_from_csv(path: str, field_map: Optional[Dict[str, str]] = None) -> List[Player]:
    p = Path(path)
    field_map = field_map or {}
    result: List[Player] = []
    with p.open('r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get(field_map.get('name', 'name')) or row.get('name')
            club = row.get(field_map.get('club', 'club')) or row.get('club') or ''
            league = row.get(field_map.get('league', 'league')) or row.get('league') or ''
            position = row.get(field_map.get('position', 'position')) or row.get('position') or None
            if not name:
                continue
            result.append(Player(name=name.strip(), club=club.strip(), league=league.strip(), position=(position or '').strip() or None))
    return result
