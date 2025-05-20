from logging.config import fileConfig
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy import pool
from alembic import context
from database.models import Base  # Импортируйте вашу базовую модель

# Alembic Config object, который предоставляет доступ к настройкам из .ini файла
config = context.config

# Настройка логирования
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Укажите вашу метаинформацию для автогенерации
target_metadata = Base.metadata
print("Таблицы в моделях:", list(Base.metadata.tables.keys()))


def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' режиме.

    В этом режиме используется URL для подключения,
    и движок базы данных не создаётся.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме.

    В этом режиме создаётся асинхронный движок базы данных
    и подключение к нему.
    """
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection):
    """Выполнение миграций."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
