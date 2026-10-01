import asyncio

from alembic import command

from tests.conftest import alembic_config


async def test_models_match_migrations(api_database_url: str) -> None:
    # `alembic check` fails if autogenerate would produce a new migration.
    await asyncio.to_thread(command.check, alembic_config(api_database_url))
