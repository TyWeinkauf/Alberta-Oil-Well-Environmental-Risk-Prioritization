"""Make repository scripts runnable from any working directory without installation."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_cli(action):
    """Return useful failures without printing a connection URL or credentials."""
    try:
        action()
    except ValueError as exc:
        print(f'Configuration/validation error: {exc}', file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as exc:
        print(f'Operation failed ({type(exc).__name__}). Check local PostgreSQL/PostGIS, '
              'DATABASE_URL, write permissions and README.md. No connection credentials logged.',
              file=sys.stderr)
        raise SystemExit(1) from None
