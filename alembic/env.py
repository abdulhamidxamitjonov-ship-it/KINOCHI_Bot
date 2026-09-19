import asyncio
from logging.config import fileConfig
from alembic import context
from app.database.models import Base
from app.config import settings

config=context.config
if config.config_file_name: fileConfig(config.config_file_name)
target_metadata=Base.metadata

def run_migrations_online():
    from sqlalchemy.ext.asyncio import create_async_engine
    url=settings.database_url
    engine=create_async_engine(url)
    async def run():
        async with engine.connect() as connection:
            await connection.run_sync(lambda c: context.configure(connection=c,target_metadata=target_metadata))
            await connection.run_sync(lambda c: context.run_migrations())
    asyncio.run(run())
run_migrations_online()
