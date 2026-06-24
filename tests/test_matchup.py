import math
import pytest

from worldcup_ranker.analytics import (
    defensive_profile,
    tournament_defensive_ranges,
    defensive_vulnerability,
    matchup_scores,
    DEFAULT_MATCHUP_WEIGHTS,
    _MATCHUP_AXES,
)


# ── Fixture factory ───────────────────────────────────────────────────────────

def _make_player(name, position, goals=0.0, xG=0.0, assists=0.0, xA=0.0,
                 overall=70.0, rating=7.0, minutes=900):
    """Minimal player profile matching the real data model."""
    return {
        'name': name,
        'aliases': [name.lower()],
        'minutes': minutes,
        'matches': 10,
        'aggregated': {
            'minutes': minutes,
            'matches': 10,
            'goals': goals,
            'assists': assists,
            'xG': xG,
            'xA': xA,
            'overall': overall,
            'rating': rating,
        },
        'raw': [{'provider': 'test', 'record': {'position': position}}],
    }


# ── defensive_profile ─────────────────────────────────────────────────────────

def test_defensive_profile_uses_def_gk_only():
    squad = [
        _make_player("Striker",    "FW",  goals=0.8, xG=0.7),
        _make_player("Midfielder", "MF",  goals=0.3, xG=0.3),
        _make_player("Defender",   "DEF", goals=0.05, xG=0.05),
        _make_player("Keeper",     "GK",  goals=0.0,  xG=0.0),
    ]
    profile = defensive_profile(squad, axes=["goals_per90", "xG_per90"])
    # DEF goals/90 = 0.05/900*90 = 0.005, GK = 0.0 → mean = 0.0025
    # FWD and MID should be excluded
    assert profile["goals_per90"] == pytest.approx(0.0025, abs=1e-4)


def test_defensive_profile_fallback_on_no_def():
    squad = [
        _make_player("Striker A", "FW", goals=0.5),
        _make_player("Striker B", "FW", goals=1.0),
    ]
    # No DEF/GK — should not raise and should use full squad
    profile = defensive_profile(squad, axes=["goals_per90"])
    assert "goals_per90" in profile
    assert not math.isnan(profile["goals_per90"])


# ── tournament_defensive_ranges ───────────────────────────────────────────────

def test_tournament_defensive_ranges_spans_both_teams():
    squads = {
        "TeamA": [_make_player("D1", "DEF", goals=0.1)],
        "TeamB": [_make_player("D2", "DEF", goals=0.5)],
    }
    ranges = tournament_defensive_ranges(squads, axes=["goals_per90"])
    mn, mx = ranges["goals_per90"]
    # goals/90 for D1 = 0.1/900*90 ≈ 0.01, for D2 ≈ 0.05
    assert mn < mx
    assert mn <= 0.011
    assert mx >= 0.049


def test_tournament_defensive_ranges_guard_zero_width():
    # Two defenders with identical values — range must not be zero-width
    squads = {
        "TeamA": [_make_player("D1", "DEF", goals=0.2)],
        "TeamB": [_make_player("D2", "DEF", goals=0.2)],
    }
    ranges = tournament_defensive_ranges(squads, axes=["goals_per90"])
    mn, mx = ranges["goals_per90"]
    assert mx > mn


# ── defensive_vulnerability ───────────────────────────────────────────────────

def test_vulnerability_inverted():
    def_ranges = {"goals_per90": (0.0, 1.0)}

    # Team at tournament maximum → strongest defence → vulnerability ≈ 0
    strong = {"goals_per90": 1.0}
    vuln_strong = defensive_vulnerability(strong, def_ranges)
    assert vuln_strong["goals_per90"] == pytest.approx(0.0, abs=1e-6)

    # Team at tournament minimum → weakest defence → vulnerability ≈ 1
    weak = {"goals_per90": 0.0}
    vuln_weak = defensive_vulnerability(weak, def_ranges)
    assert vuln_weak["goals_per90"] == pytest.approx(1.0, abs=1e-6)


def test_vulnerability_nan_defaults_to_neutral():
    def_ranges = {"goals_per90": (0.0, 1.0)}
    profile = {"goals_per90": float("nan")}
    vuln = defensive_vulnerability(profile, def_ranges)
    assert vuln["goals_per90"] == pytest.approx(0.5)


def test_vulnerability_missing_key_defaults_to_neutral():
    def_ranges = {"goals_per90": (0.0, 1.0)}
    profile = {}  # no goals_per90 key
    vuln = defensive_vulnerability(profile, def_ranges)
    assert vuln["goals_per90"] == pytest.approx(0.5)


# ── matchup_scores ────────────────────────────────────────────────────────────

def _simple_squads():
    """Three-team squads with predictable stats for ranking tests."""
    return {
        "TeamA": [
            _make_player("High Scorer", "FW",  goals=1.5, xG=1.2, overall=85.0),
            _make_player("Mid Scorer",  "MF",  goals=0.5, xG=0.4, overall=78.0),
            _make_player("Low Scorer",  "DEF", goals=0.1, xG=0.1, overall=72.0),
            _make_player("GK Player",   "GK",  goals=0.0, xG=0.0, overall=80.0),
        ],
        "TeamB": [
            _make_player("B Defender", "DEF", goals=0.0, xG=0.0, overall=68.0),
            _make_player("B Keeper",   "GK",  goals=0.0, xG=0.0, overall=65.0),
        ],
        "TeamC": [
            _make_player("C Defender", "DEF", goals=0.1, xG=0.1, overall=82.0),
        ],
    }


def test_matchup_scores_rank_order():
    squads = _simple_squads()
    results = matchup_scores(squads["TeamA"], squads["TeamB"], squads)
    assert len(results) >= 2
    # Scores should be in descending order
    scores = [r["matchup_score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    # High Scorer should rank above Low Scorer
    names = [r["name"] for r in results]
    assert names.index("High Scorer") < names.index("Low Scorer")


def test_matchup_scores_excludes_gk():
    squads = _simple_squads()
    results = matchup_scores(squads["TeamA"], squads["TeamB"], squads)
    names = [r["name"] for r in results]
    assert "GK Player" not in names


def test_matchup_scores_includes_def():
    squads = _simple_squads()
    results = matchup_scores(squads["TeamA"], squads["TeamB"], squads)
    names = [r["name"] for r in results]
    assert "Low Scorer" in names


def test_matchup_scores_nan_robust():
    squads = {
        "TeamA": [_make_player("NaN Player", "FW", goals=float("nan"), xG=float("nan"),
                               assists=float("nan"), xA=float("nan"), overall=float("nan"),
                               rating=float("nan"))],
        "TeamB": [_make_player("B Def", "DEF")],
    }
    results = matchup_scores(squads["TeamA"], squads["TeamB"], squads)
    assert len(results) == 1
    assert results[0]["matchup_score"] == pytest.approx(0.0)


def test_matchup_scores_zero_weight():
    squads = _simple_squads()
    zero_weights = {a: 0.0 for a in DEFAULT_MATCHUP_WEIGHTS}
    results = matchup_scores(squads["TeamA"], squads["TeamB"], squads, weights=zero_weights)
    for r in results:
        assert r["matchup_score"] == pytest.approx(0.0)


def test_matchup_scores_returns_axis_contributions():
    squads = _simple_squads()
    results = matchup_scores(squads["TeamA"], squads["TeamB"], squads)
    for r in results:
        assert "axis_contributions" in r
        assert set(r["axis_contributions"].keys()) == set(_MATCHUP_AXES)
