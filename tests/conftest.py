"""Make `scripts/` importable as a top-level package regardless of invocation cwd."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
