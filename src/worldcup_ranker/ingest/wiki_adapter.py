import re
import urllib.request
from typing import Dict, List

from worldcup_ranker.match_utils import normalise_name

_SKIP_HEADINGS = {
    'contents', 'references', 'external links', 'see also', 'notes',
    'navigation menu', 'further reading', 'bibliography',
}
_EDIT_RE = re.compile(r'\[edit\]|\[note[^\]]*\]|\[\d+\]')


def fetch_squads_from_wikipedia(url: str) -> Dict[str, List[str]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as e:
        raise RuntimeError(
            "beautifulsoup4 is required to fetch squads from Wikipedia; "
            "install it with `pip install beautifulsoup4`."
        ) from e

    req = urllib.request.Request(url, headers={'User-Agent': 'worldcup-ranker/0.1 (research)'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode('utf-8', errors='replace')

    soup = BeautifulSoup(html, 'html.parser')
    squads: Dict[str, List[str]] = {}

    for heading in soup.find_all(['h2', 'h3']):
        raw = heading.get_text(' ', strip=True)
        team_name = _EDIT_RE.sub('', raw).strip()
        if not team_name or team_name.lower() in _SKIP_HEADINGS:
            continue

        # Modern Wikipedia wraps headings in <div class="mw-heading">; the
        # table is a sibling of that div, not of the <h2>/<h3> itself.
        parent = heading.parent
        start = parent if (parent.name == 'div' and 'mw-heading' in ' '.join(parent.get('class') or [])) else heading

        node = start.find_next_sibling()
        while node:
            if node.name in ('h2', 'h3'):
                break
            if node.name == 'div' and 'mw-heading' in ' '.join(node.get('class') or []):
                break
            if node.name == 'table':
                names = _extract_player_names(node)
                if len(names) >= 5:
                    squads[team_name] = [normalise_name(n) for n in names]
                    break
            node = node.find_next_sibling()

    return squads


def _extract_player_names(table) -> List[str]:
    rows = table.find_all('tr')
    if not rows:
        return []

    name_col = _find_name_column(rows[0])

    names = []
    for row in rows[1:]:
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue
        idx = name_col if name_col is not None and name_col < len(cells) else 0
        text = _EDIT_RE.sub('', cells[idx].get_text(' ', strip=True)).strip()
        if text and not text.isdigit():
            names.append(text)

    return names


def fetch_groups_from_wikipedia(url: str) -> Dict[str, List[str]]:
    """Parse WC group tables from a Wikipedia page.

    Looks for headings that start with "Group" (e.g. "Group A") and extracts the
    team names from the first table beneath each heading.

    Returns ``{group_label: [team_name, ...]}``, e.g.
    ``{"Group A": ["Argentina", "Canada", "Mexico", "Ecuador"]}``.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError as e:
        raise RuntimeError(
            "beautifulsoup4 is required; install it with `pip install beautifulsoup4`."
        ) from e

    req = urllib.request.Request(url, headers={'User-Agent': 'worldcup-ranker/0.1 (research)'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode('utf-8', errors='replace')

    soup = BeautifulSoup(html, 'html.parser')
    groups: Dict[str, List[str]] = {}

    for heading in soup.find_all(['h2', 'h3']):
        raw = heading.get_text(' ', strip=True)
        label = _EDIT_RE.sub('', raw).strip()
        if not label.lower().startswith('group'):
            continue

        parent = heading.parent
        start = parent if (parent.name == 'div' and 'mw-heading' in ' '.join(parent.get('class') or [])) else heading

        node = start.find_next_sibling()
        while node:
            if node.name in ('h2', 'h3'):
                break
            if node.name == 'div' and 'mw-heading' in ' '.join(node.get('class') or []):
                break
            if node.name == 'table':
                teams = _extract_group_teams(node)
                if len(teams) >= 2:
                    groups[label] = teams
                    break
            node = node.find_next_sibling()

    return groups


def _extract_group_teams(table) -> List[str]:
    """Extract team names from a WC group standings table."""
    rows = table.find_all('tr')
    if not rows:
        return []

    team_col = None
    header = rows[0].find_all(['th', 'td'])
    for i, cell in enumerate(header):
        text = cell.get_text(strip=True).lower()
        if 'team' in text or 'nation' in text:
            team_col = i
            break

    teams = []
    for row in rows[1:]:
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue
        idx = team_col if team_col is not None and team_col < len(cells) else 0
        text = _EDIT_RE.sub('', cells[idx].get_text(' ', strip=True)).strip()
        if text and not text.isdigit():
            teams.append(text)

    return teams


def _find_name_column(header_row) -> int:
    cells = header_row.find_all(['th', 'td'])
    for i, cell in enumerate(cells):
        text = cell.get_text(strip=True).lower()
        if 'name' in text or 'player' in text:
            return i
    return None
