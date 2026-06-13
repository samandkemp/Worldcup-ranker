from statistics import mean
from typing import Dict, Optional, List, Any

from worldcup_ranker.metrics.base import Metric, MetricRegistry
from worldcup_ranker.models import Player, Team


DEFAULT_LEAGUE_STRENGTHS = {
    'premier league': 100.0,
    'la liga': 95.0,
    'bundesliga': 90.0,
    'serie a': 88.0,
    'ligue 1': 82.0,
    'primeira liga': 75.0,
    'eredivisie': 74.0,
    'jupiler pro league': 70.0,
    'super lig': 68.0,
    'scottish premiership': 65.0,
    'brasileirao': 72.0,
    'liga profesional argentina': 68.0,
    'liga mx': 62.0,
    'mls': 60.0,
    'saudi pro league': 58.0,
    'uefa champions league': 98.0,
}


@MetricRegistry.register
class MeanTopLeaguePosition(Metric):
    def __init__(self, league_strengths: Dict[str, float] = None, top_n: Optional[int] = 11):
        super().__init__(name="MeanTopLeaguePosition")
        self.league_strengths = league_strengths or DEFAULT_LEAGUE_STRENGTHS
        self.top_n = top_n

    def compute(self, team: Team, players: List[Player], context: Dict[str, Any] = None) -> float:
        scores = [self.league_strengths.get(p.league.lower(), 50.0) for p in players]
        if not scores:
            return 0.0
        scores.sort(reverse=True)
        selected = scores if self.top_n is None else scores[: self.top_n]
        return mean(selected)
