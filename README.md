# World Cup 2026 Ranker

A personal analysis tool for the 2026 World Cup. Scrapes club-season stats for every player at the tournament, maps them to their national squads, and presents an interactive dashboard for team and player comparisons.

Stats are sourced from the 2024-25 club season across multiple leagues — goals, assists, xG, FIFA ratings — and normalised across all 48 squads for direct comparison. The idea is to replace pre-baked aggregate rankings with the same visualisation methods used in professional football analytics.

### Setup

Requires Python 3.8+.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

The dashboard runs at `http://localhost:8501`:

```bash
streamlit run src/worldcup_ranker/webapp.py
```

On startup, the app auto-loads from `data/squads_cache.json` if it exists from a previous fetch.

### Data pipeline

**Fetch / Refresh Data** runs the full pipeline: pulls player stats from FBref, Understat, SoFIFA, and SofaScore across the selected leagues, fuzzy-matches player names across providers, and cross-references Wikipedia's squad lists to assign players to national teams. Results are cached to `data/squads_cache.json`; subsequent loads are instant.

**Fetch WC Match Data** pulls in-tournament stats (goals, assists, xG, xA, minutes) from FBref and attaches them to existing player profiles as `wc_stats`. Only meaningful once FBref has competition data for the relevant season.

**Sidebar settings:**

- **Season code** — `2425` is the 2024-25 club season, the most recently completed domestic season for a June 2026 tournament.
- **Leagues** — seven selected by default (Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Primeira Liga, Eredivisie). Additional leagues improve coverage for players in the Turkish Super Lig, Brazilian Serie A, MLS, Saudi Pro League, etc.
- **Min. club minutes** — filters the per-90 stats shown in charts to players above a minutes threshold; defaults to 500.
- **Find a player** — substring search across all loaded squad data, shown inline above the tab bar.

### Dashboard

**Team Comparison** — six-axis radar (Goals/90, xG/90, Assists/90, xA/90, FIFA Overall, SofaScore rating) for two selected nations. All axes are normalised against all 48 squads, so 100% on any spoke means the tournament high for that stat. Team values are the mean of the top 11 players by minutes — an approximation of the likely starting XI. Coverage (matched/squad size) appears under each team name. Aggregated stats and a position-group radar sit below.

**Player Comparison** — same per-tournament normalisation as team comparison but applied per player across all squad players. **Position-appropriate axes** restricts the radar to spokes relevant to each player's role. **Show WC stats** swaps to in-tournament data once WC match data has been loaded. Full stats table with CSV export below the radar.

**Squad Explorer** — full drill-down for a single nation: top-N bar chart for any metric, xG vs xA scatter (bubble size = minutes), club contribution pie, position-group radar, and CSV export.

**Rankings** — all 48 squads sorted by ELO-style strength rating (centred at 1500; above-average squads score above 1500). Coverage per squad shown alongside. Violin plot shows the distribution of any metric across all teams. Downloadable as CSV.

**Group Stage** — parses WC2026 group composition from Wikipedia and shows each team's strength rating, coverage, and key stats within their group.

### Data model

Player profiles carry an `aggregated` dict of season stats. After WC data is fetched, a `wc_stats` dict is attached with in-tournament figures. All per-90 metrics in the dashboard derive from these at render time.

Coverage gaps come from two sources: players in leagues outside the current selection have no FBref/Understat numbers; players whose names transliterate differently between FBref and Wikipedia (common with Arabic, Japanese, and Portuguese names) may not match at the fuzzy-matching stage. Both cases show as the minimum end of the normalised range on radar charts. Provider-level fetch failures surface in a collapsible warnings section in the sidebar.

Raw provider data is cached to `data/raw_sources.json`. The processed squad data (already merged and matched) is in `data/squads_cache.json`, which is what auto-load uses on startup. Force refresh re-runs the full scrape against the raw provider APIs.

### Known behaviours

**"No squad data found"** — Wikipedia squad URL format changed; squad tables are expected under country-level headings. Tournament pages often restructure mid-event.

**Low player counts per team** — the selected leagues don't cover those squads. BEL-First Division A, TUR-Super Lig, BRA-Serie A, and ARG-Liga Profesional improve coverage for African, South American, and MENA nations.

**Missing individual player** — not in a selected league, or name matching failed between FBref and Wikipedia. No manual override.

**Group Stage shows "no data"** — Wikipedia uses headings like "Group A" for group tables; mid-tournament these often get renamed or restructured. The specific group-stage sub-article may have cleaner markup.

**WC match data unavailable** — FBref may not yet have the competition listed, or the season identifier doesn't match. Expected before the tournament opens.

**Slow fetch** — FBref and similar sources rate-limit requests; `soccerdata` handles this transparently. Fewer leagues reduces fetch time.

### Project layout

```
src/worldcup_ranker/
├── webapp.py            — Streamlit dashboard (5 tabs)
├── pipeline.py          — fetch_for_leagues(), enrich_with_tournament_stats()
├── analytics.py         — per-90 calculations and Plotly chart functions
├── merge.py             — fuzzy deduplication across data providers
├── normaliser.py        — league name aliases (~40 leagues)
├── match_utils.py       — name normalisation + fuzzy matching
├── ranking.py           — MetricRegistry-based team ranking
├── models.py            — Player and Team dataclasses
├── storage.py / db.py   — JSON caching layer (raw_sources.json + squads_cache.json)
├── ingest/
│   ├── soccerdata_adapter.py   — FBref, Understat, SoFIFA, SofaScore
│   ├── wiki_adapter.py         — Wikipedia squad + group parser
│   └── csv_adapter.py          — load players from a local CSV file
└── metrics/
    ├── base.py                       — abstract Metric class + MetricRegistry
    └── mean_top_league_position.py   — default league-strength scoring
```

### Developer reference

**Tests**

```bash
python -m pytest tests/ -v
```

**Pipeline API**

```python
from worldcup_ranker.pipeline import fetch_for_leagues, enrich_with_tournament_stats

squads, squad_sizes, warnings = fetch_for_leagues(
    leagues=["ENG-Premier League", "ESP-La Liga", ...],
    season="2425",
    tournament_wiki_url="https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads",
    storage_path="data/",
    force_refresh=False,
)

squads, warnings = enrich_with_tournament_stats(squads, tournament="FIFA World Cup", season="2026")
```

`fetch_for_leagues` returns `(squads, squad_sizes, warnings)` where `squad_sizes` is `{country: total_wiki_squad_size}` for computing coverage percentages.

**Metrics**

New metrics implement the `Metric` interface and self-register via `@MetricRegistry.register`:

```python
from worldcup_ranker.metrics.base import Metric, MetricRegistry
from worldcup_ranker.models import Team

@MetricRegistry.register
class MyMetric(Metric):
    def compute(self, team: Team, players, context=None) -> float:
        ...
```

Available via `ranking.compute_metric(team, 'MyMetric')`.

**Data providers**

New provider adapters are `fetch_*` functions in `soccerdata_adapter.py` returning a list of dicts with at least a `name` key. They're wired in by calling them inside `fetch_providers_for_competition` in `pipeline.py`, following the same error-handling pattern as the existing providers.
