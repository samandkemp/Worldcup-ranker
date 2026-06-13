from worldcup_ranker.models import Player, Team
from worldcup_ranker.ranking import team_mean_top_league_position, DEFAULT_LEAGUE_STRENGTHS


def test_team_mean_top_league_position_basic():
    players = [
        Player('P1','C1','Premier League'),
        Player('P2','C2','La Liga'),
        Player('P3','C3','Bundesliga'),
    ]
    team = Team('T', players)
    score = team_mean_top_league_position(team, DEFAULT_LEAGUE_STRENGTHS, top_n=3)
    assert score > 0
