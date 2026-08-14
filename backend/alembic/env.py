from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db import Base
from app.models import user  # noqa: F401 — registers User with Base.metadata
from app.models import content  # noqa: F401 — registers content models with Base.metadata
from app.models import note  # noqa: F401 — registers note models with Base.metadata
from app.models import question  # noqa: F401 — registers question models with Base.metadata
from app.models import mastery  # noqa: F401 — registers mastery models with Base.metadata
from app.models import review  # noqa: F401 — registers review models with Base.metadata
from app.models import focus  # noqa: F401 — registers focus models with Base.metadata
from app.models import lab  # noqa: F401 — registers lab models with Base.metadata
from app.models import gamification  # noqa: F401 — registers gamification models with Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
