import unicodedata
import re
from typing import List
from functools import lru_cache

try:
    from rapidfuzz import process, fuzz  # type: ignore
    _HAS_RAPIDFUZZ = True
except Exception:
    _HAS_RAPIDFUZZ = False
    from difflib import get_close_matches  # fallback


_NON_ALNUM_RE = re.compile(r'[^a-z0-9\s]')
_MULTI_SPACE_RE = re.compile(r'\s+')


@lru_cache(maxsize=8192)
def normalise_name(name: str) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = _NON_ALNUM_RE.sub('', s)
    s = _MULTI_SPACE_RE.sub(' ', s)
    return s


def fuzzy_match(name: str, choices: List[str], cutoff: float = 0.85) -> List[str]:
    if not name or not choices:
        return []
    if _HAS_RAPIDFUZZ:
        threshold = int(cutoff * 100)
        results = process.extract(name, choices, scorer=fuzz.token_sort_ratio, limit=5)
        return [r[0] for r in results if r[1] >= threshold]
    else:
        return get_close_matches(name, choices, n=5, cutoff=cutoff)
