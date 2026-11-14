"""Use both declared package source roots for source-level tests only."""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'apps/core/src'))
import zizai

connector_root = str(REPO / 'apps/connectors/src/zizai')
if connector_root not in zizai.__path__:
    zizai.__path__.append(connector_root)
