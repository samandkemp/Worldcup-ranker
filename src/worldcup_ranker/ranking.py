from typing import Dict, Optional, List, Any

from worldcup_ranker.models import Player, Team
from worldcup_ranker.metrics import MetricRegistry
from worldcup_ranker.metrics.mean_top_league_position import DEFAULT_LEAGUE_STRENGTHS


def compute_metric(team: Team, metric_name: str, players: Optional[List[Player]] = None, **kwargs) -> float:
    players = players or team.players
    metric = MetricRegistry.create(metric_name, **kwargs)
    return metric.compute(team, players)


def team_mean_top_league_position(team: Team, league_strengths: Dict[str, float] = None, top_n: Optional[int] = 11) -> float:
    metric = MetricRegistry.create('MeanTopLeaguePosition', league_strengths=league_strengths, top_n=top_n)
    return metric.compute(team, team.players)


__all__ = ["compute_metric", "team_mean_top_league_position", "DEFAULT_LEAGUE_STRENGTHS"]
