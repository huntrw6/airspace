from pathlib import Path

from alembic import command
from alembic.config import Config

from .database import engine


def upgrade_database() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
