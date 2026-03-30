from __future__ import annotations

from tortoise.config import AppConfig, DBUrlConfig
from tortoise.config import TortoiseConfig as TortoiseORMConfig

from app.config import config

from ..db import TORTOISE_MIGRATIONS, TORTOISE_MODELS

TORTOISE_ORM = TortoiseORMConfig(
    connections={
        "default": DBUrlConfig(config.database.dsn),
    },
    apps={
        "models": AppConfig(
            models=TORTOISE_MODELS,
            migrations=TORTOISE_MIGRATIONS,
        ),
    },
)
