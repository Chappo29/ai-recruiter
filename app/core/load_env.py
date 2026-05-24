from pathlib import Path


def load_project_env() -> None:
    """Load `.env` from project root if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
