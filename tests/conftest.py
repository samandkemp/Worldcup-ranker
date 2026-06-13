import sys
from pathlib import Path

# Ensure the `src` directory is on sys.path so imports resolve during tests
ROOT = Path(__file__).resolve().parent
# project_root is the parent of the tests directory
project_root = ROOT.parent
SRC = project_root / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
