# World Cup 2026 Ranker

A personal analysis tool for the 2026 World Cup. It scrapes live club stats for every player at the tournament, maps them to their national squads, and gives you an interactive dashboard to explore team and player comparisons.

The idea is simple: instead of using pre-baked ratings or aggregate squad rankings, you pull the actual stats from the current club season — goals, assists, expected goals, FIFA ratings — and see how squads stack up against each other using the same visualisation methods used in professional football analytics.

---

## Before you start

You'll need Python 3.8 or newer. Check with:

```bash
python --version
```

You'll also need `soccerdata` installed, which is what fetches the actual stats data. It makes requests to FBref, Understat, and others, so you need a working internet connection the first time you run a fetch.

---

## Setting up

Clone or download the project, then open a terminal in the project folder and run:

```bash
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

That's it. You don't need to configure anything else before running.

---

## Running the dashboard

From the project root folder, with your virtual environment active:

```bash
streamlit run src/worldcup_ranker/webapp.py
```

This opens the app in your browser at `http://localhost:8501`.

If you've run a fetch before, the app will auto-load the last saved data on startup — you'll see the team and player count in the sidebar straight away without clicking anything. If it's your first run, you'll see a message telling you to fetch data.

---

## Fetching data for the first time

Everything happens through the sidebar on the left.

**Step 1 — Check the settings**

The defaults are sensible for WC2026. You shouldn't need to change anything unless you want to customise:

- **Wikipedia squads URL** — pre-filled to the Wikipedia page listing all 48 WC2026 national squads. If Wikipedia's page structure changes mid-tournament, you might need to update this.
- **Season code** — `2425` means the 2024-25 club season, which is where player stats are pulled from. For a tournament happening in summer 2026, this is the most recently completed domestic season for most leagues.
- **Leagues to scrape** — seven are selected by default (Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Primeira Liga, Eredivisie). These cover the majority of WC2026 squad players. You can add more from the dropdown to improve coverage of players in the Turkish Super Lig, Brazilian Serie A, MLS, Saudi Pro League, etc.

**Step 2 — Click "Fetch / Refresh Data"**

The first fetch takes a few minutes. It pulls data from multiple sources (FBref, Understat, SoFIFA, SofaScore) across each selected league, merges player records across providers using fuzzy name matching, then cross-references against the Wikipedia squad lists to assign each player to their national team.

Once done, the sidebar shows how many teams and players were loaded, and a timestamp of when the data was fetched. Subsequent app launches auto-load from the local cache instantly.

**Step 3 — Optionally fetch WC match stats**

Once the tournament is underway, click **"Fetch WC Match Data"** in the sidebar. This pulls in-tournament stats (goals, assists, xG, xA, minutes played) directly from FBref and attaches them to each player's profile. You can then toggle between club-season stats and WC-tournament stats in the Player Comparison tab.

This button is greyed out until you've run the main fetch first. If the tournament hasn't started yet or FBref doesn't have data for it, you'll see a warning in the sidebar — everything else still works normally.

---

## Sidebar controls

Beyond the fetch buttons, the sidebar has two display controls that affect what you see across all tabs:

**Min. club minutes played** — a slider (default 500) that hides players with less than that many club minutes. This reduces noise from squad players who barely featured at their club. Lowering it to zero shows the full squad; raising it focuses on regular starters.

**Find a player** — type any part of a player's name and matching results appear above the tabs, showing their key stats inline. Useful for quickly locating a specific player without having to know their squad first.

---

## Using the dashboard

### Team Comparison

Pick two nations from the dropdowns. You'll get:

**Radar chart** — the six spokes are Goals/90, xG/90, Assists/90, xA/90, FIFA Overall rating, and SofaScore rating. Every axis is *normalised against all 48 squads*, not shown as raw numbers. So if a spoke is at 100%, that team has the highest value for that stat across the whole tournament. This makes it easy to see where a team punches above or below average without needing to interpret raw football stats.

The radar averages the top 11 players by minutes played for each team, which approximates the likely starting XI rather than the full 26-man squad.

**Coverage** — underneath each team name you'll see something like "22 / 26 players matched". This tells you how many of Wikipedia's squad list the tool was able to find stats for. If a squad has low coverage it usually means those players are in leagues not selected for scraping.

**Aggregated stats** — the raw figures: average goals per 90, weighted xG per 90 (minutes-weighted so rotational players don't drag down the average), assists, and mean FIFA overall.

**Position profiles** — a separate radar broken out by position group (GK, DEF, MID, FWD). Useful for spotting whether a team's strength comes from their attack or their midfield.

---

### Player Comparison

Pick a team on each side, then pick a player from each squad. The comparison works the same way as the team radar — values are normalised across every player at the tournament so the chart is immediately interpretable regardless of position.

**Options at the top right:**

- **Position-appropriate axes** — when checked, the radar only shows axes relevant to each player's role. A goalkeeper comparison won't show goals per 90 axes; a pure defender will show assists and xA but not goal threat spokes. This gives a fairer read when comparing players of similar positions.
- **Show WC stats** — when WC match data has been fetched, toggling this switches the radar (and the stats table) from club season stats to what the player has actually done in the tournament. Only available after clicking "Fetch WC Match Data" in the sidebar.

Below the radar is a full stats table: total minutes, matches, goals, assists, xG, xA, all the per-90 versions, and ratings. If WC data is loaded, tournament stats appear in a separate section of the same table. There's a **Download stats as CSV** button at the bottom.

A note on the data: not every player will have every stat. A player in a league not in your selection won't have FBref/Understat numbers. Where data is missing the axis defaults to the minimum end of the normalised range, which means a blank spoke doesn't mean zero — it means no data was found.

---

### Squad Explorer

Select a nation to drill into their full squad.

**Coverage note** — the header shows how many players from Wikipedia's squad list were matched. Low numbers here usually mean adding more leagues to your selection would help.

**Top players bar** — shows the top N players for whichever metric you pick (Goals/90, xG/90, etc.). Use the slider to adjust how many players to show.

**xG vs xA scatter** — each bubble is a player, positioned by expected goals and expected assists. Bubble size shows total minutes played. Players in the top-right corner are both goal threats and creative. Big bubbles are the minutes-heavy regulars.

**Club minutes pie** — shows which clubs are contributing the most to this national squad by total minutes played.

**Position radar** — how each position group compares on attacking metrics. A strong MID spoke with a weak FWD spoke suggests the team relies on midfield creativity rather than a dominant striker.

**Download squad stats as CSV** — exports all per-90 metrics for the full squad to a CSV file.

---

### Rankings

A sortable table of all 48 squads ranked by strength rating. The strength score is a composite derived from minutes-weighted player values — it uses FIFA overall rating where available, then falls back to a formula combining goals, xG, and assists per 90. It's centred around 1500 (similar to ELO) so anything above 1500 is above the tournament average.

The **Coverage** column shows matched/total for each squad. The table is downloadable as CSV.

Below the table is a violin plot for any metric you choose, showing the full distribution across all teams. The fat parts of each violin show where teams cluster; outlier dots show the genuine top and bottom performers. Good for understanding whether a metric is broadly even across the field or has clear outliers.

---

### Group Stage

Click **"Load Groups from Wikipedia"** to parse the WC2026 group tables directly from the tournament's Wikipedia page. This gives you a breakdown of all groups with each team's strength rating, coverage, and key stats side by side within the group.

The page URL is pre-filled. If Wikipedia has moved the group tables to a different section (common during the tournament as the live results replace them), you may need to try the specific group-stage sub-page instead.

---

## Things worth knowing

**The first fetch is slow, everything after is fast.** Raw provider data is cached to `data/raw_sources.json`. The processed squad data (with player profiles already merged and matched) is saved separately to `data/squads_cache.json`, which is what the auto-load uses on startup. Force refresh re-runs the full scrape; loading from the sidebar without force refresh reads from the raw cache.

**Some players won't appear.** Player names are matched across providers using fuzzy text matching, then matched again against Wikipedia's squad names. If a name is transliterated differently between FBref and Wikipedia (common with Arabic, Japanese, or Portuguese names) it may not match. Players who predominantly play in leagues not in your selected set will also have limited stats.

**Stats reflect club performance, not international.** This tool shows how players have performed at club level during the 2024-25 season. It doesn't account for international form, fitness coming into the tournament, or tactical roles that differ from club football. Use the WC stats toggle once the tournament is underway for in-tournament data.

**Provider warnings in the sidebar.** Some data sources occasionally fail or return no data for specific league/season combinations. If a fetch partially fails, warnings appear in the sidebar under a collapsible section. The app will still work with whatever data came through successfully.

---

## When something goes wrong

**"No squad data found" after fetching** — the Wikipedia squad URL might have changed structure. Try opening it in a browser to check it still lists squad tables under team headings (one `<h2>` or `<h3>` per country followed by a table). If the page has been reorganised, you may need to try an alternative URL.

**Very few players showing per team** — this usually means the selected leagues don't cover that team's players. Adding BEL-First Division A, TUR-Super Lig, BRA-Serie A, and ARG-Liga Profesional helps with African, South American, and MENA squads.

**A specific player is missing** — they likely play in a league not in your selection, or their name failed to fuzzy-match between FBref and the Wikipedia squad list. There's no manual workaround currently.

**Group Stage tab shows "no data" for teams** — group name parsing depends on Wikipedia using headings like "Group A". Mid-tournament these sections often get renamed to "Group A standings" or similar; try reloading groups with the URL for the specific group-stage article.

**"Fetch WC Match Data" fails** — the competition may not yet be listed on FBref, or the season identifier doesn't match. This is expected before the tournament starts; a warning appears in the sidebar and everything else continues working normally.

**Fetch takes longer than 10 minutes** — FBref and others rate-limit requests. `soccerdata` handles this automatically but it can slow things down with many leagues selected. Try fetching with fewer leagues first.

---

## Refreshing during the tournament

WC2026 runs June to July 2026. To get the freshest possible data:

1. Keep the season code as `2425` — this covers the most recently completed domestic season for most leagues
2. Add extra leagues from the dropdown if you want better squad coverage
3. Tick **Force refresh** before any key match to pull the latest club ratings
4. Click **Fetch WC Match Data** after each round of games to pull in-tournament goals, assists, and xG from FBref

---

## For developers

### Project structure

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

### Key pipeline functions

```python
from worldcup_ranker.pipeline import fetch_for_leagues, enrich_with_tournament_stats

# Fetch club stats across multiple leagues and filter to WC squads
squads, squad_sizes, warnings = fetch_for_leagues(
    leagues=["ENG-Premier League", "ESP-La Liga", ...],
    season="2425",
    tournament_wiki_url="https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads",
    storage_path="data/",
    force_refresh=False,
)

# Attach WC in-tournament stats to player profiles
squads, warnings = enrich_with_tournament_stats(squads, tournament="FIFA World Cup", season="2026")
```

`fetch_for_leagues` returns `(squads, squad_sizes, warnings)` where `squad_sizes` is a dict of `{country: total_wiki_squad_size}` for computing coverage percentages. Processed squads are saved to `data/squads_cache.json` automatically.

### Adding a new metric

Create a file in `src/worldcup_ranker/metrics/` and register it:

```python
from worldcup_ranker.metrics.base import Metric, MetricRegistry
from worldcup_ranker.models import Player, Team

@MetricRegistry.register
class MyMetric(Metric):
    def compute(self, team: Team, players, context=None) -> float:
        # return a single float score for the team
        ...
```

Then use it anywhere with:

```python
from worldcup_ranker.ranking import compute_metric
score = compute_metric(team, 'MyMetric')
```

### Adding a new data provider

Add a `fetch_*` function to `src/worldcup_ranker/ingest/soccerdata_adapter.py` following the same pattern as `fetch_fbref_player_stats` — return a list of dicts with at least a `name` key. Then call it inside `fetch_providers_for_competition` in `pipeline.py` and handle exceptions the same way the existing providers do.

### Running tests

```bash
python -m pytest tests/ -v
```

### Checking all imports work

```bash
python scripts/import_check.py
```
