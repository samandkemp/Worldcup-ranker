"""Quick smoke-test that all package modules import cleanly."""
import importlib
import sys
from pathlib import Path

here = Path(__file__).resolve()
repo_root = here.parent.parent
src_dir = str(repo_root / 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

MODULES = [
    'worldcup_ranker',
    'worldcup_ranker.models',
    'worldcup_ranker.normaliser',
    'worldcup_ranker.match_utils',
    'worldcup_ranker.db',
    'worldcup_ranker.storage',
    'worldcup_ranker.merge',
    'worldcup_ranker.analytics',
    'worldcup_ranker.ranking',
    'worldcup_ranker.pipeline',
    'worldcup_ranker.cli',
    'worldcup_ranker.metrics',
    'worldcup_ranker.metrics.base',
    'worldcup_ranker.metrics.mean_top_league_position',
    'worldcup_ranker.ingest.csv_adapter',
    'worldcup_ranker.ingest.wiki_adapter',
    'worldcup_ranker.ingest.soccerdata_adapter',
]

ok = 0
fail = 0
for mod in MODULES:
    try:
        importlib.import_module(mod)
        print(f'  OK  {mod}')
        ok += 1
    except Exception as e:
        print(f'FAIL  {mod}: {e}')
        fail += 1

print(f'\n{ok} ok, {fail} failed')
sys.exit(1 if fail else 0)
