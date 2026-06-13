from .csv_adapter import load_players_from_csv
from .soccerdata_adapter import fetch_fbref_player_stats, fetch_understat_xg, fetch_sofifa_attributes, fetch_sofascore_season_updates, map_to_player
from .wiki_adapter import fetch_squads_from_wikipedia

__all__ = [
    'load_players_from_csv',
    'fetch_fbref_player_stats',
    'fetch_understat_xg',
    'fetch_sofifa_attributes',
    'fetch_sofascore_season_updates',
    'map_to_player',
    'fetch_squads_from_wikipedia',
]
