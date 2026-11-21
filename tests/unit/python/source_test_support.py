"""Find fixture connectors when testing the installed runtime."""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'connectors/csv'))
sys.path.insert(0, str(REPO / 'connectors/excel'))
