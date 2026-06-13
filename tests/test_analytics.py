import math
from worldcup_ranker import analytics


def make_profile(name, minutes, goals=0, assists=0, xG=0.0, xA=0.0, overall=None, position=None, club='Club'):
    agg = {
        'minutes': minutes,
        'matches': max(1, minutes // 90),
        'goals': goals,
        'assists': assists,
        'xG': xG,
        'xA': xA,
        'overall': overall,
    }
    raw = [{'provider': 'test', 'record': {'club': club, 'position': position}}]
    return {'name': name, 'aggregated': agg, 'raw': raw}


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_per90_and_team_aggregates():
    p1 = make_profile('A', minutes=900, goals=5, assists=2, xG=4.2, xA=1.1)
    p2 = make_profile('B', minutes=450, goals=2, assists=1, xG=1.4, xA=0.6)
    rows = [analytics.per90_metrics(p1), analytics.per90_metrics(p2)]
    assert approx(rows[0]['goals_per90'], 5 / 900 * 90)
    assert approx(rows[1]['assists_per90'], 1 / 450 * 90)

    team_agg = analytics.compute_team_aggregates([p1, p2])
    assert team_agg['players'] == 2
    assert 'mean_goals_per90' in team_agg


def test_position_aggregates_and_radar():
    p_fw = make_profile('F1', minutes=600, goals=4, position='FW')
    p_def = make_profile('D1', minutes=800, goals=0, position='DEF')
    buckets = analytics.position_aggregates([p_fw, p_def])
    assert 'FWD' in buckets or 'Unknown' in buckets
    fig = analytics.position_radar_figure([p_fw, p_def])
    assert fig is None or hasattr(fig, 'to_html')


def test_team_elo_rating_relative():
    # stronger team: higher attacking numbers
    strong = make_profile('S1', minutes=900, goals=8, assists=4, xG=6.0)
    weak = make_profile('W1', minutes=900, goals=1, assists=0, xG=0.8)
    elo_strong = analytics.team_elo_rating([strong], all_teams_profiles={'A': [strong], 'B': [weak]})
    elo_weak = analytics.team_elo_rating([weak], all_teams_profiles={'A': [strong], 'B': [weak]})
    assert elo_strong != elo_weak
    assert elo_strong > elo_weak
