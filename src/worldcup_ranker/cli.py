from worldcup_ranker.models import Player, Team
from worldcup_ranker.ranking import team_mean_top_league_position


def demo():
    players = [
        Player('Alice','Arsenal','Premier League'),
        Player('Bob','Real Madrid','La Liga'),
        Player('Carlos','Bayern','Bundesliga'),
        Player('Dina','Juventus','Serie A'),
        Player('Evan','PSG','Ligue 1'),
    ]
    roster = (players * 3)[:11]
    team = Team('Exampleland', roster)
    score = team_mean_top_league_position(team)
    print(f"Team {team.name} mean top-league score: {score:.2f}")


if __name__ == '__main__':
    demo()
