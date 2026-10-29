import os
from pathlib import Path


def data_root() -> Path:
    path = Path(os.environ.get("CHESS4F_DATA", "data")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_agent() -> str:
    return os.environ.get("CHESS4F_USER_AGENT", "chess4f/0.1 (personal research project)")
