import logging

import pytest
from sqlmodel import SQLModel

from core.services.players.models import PlayersDataBase

logger = logging.getLogger()
logger.info("%s", PlayersDataBase.__name__)


# noinspection PyShadowingNames
@pytest.mark.asyncio
async def test_mysql(database):
    assert database


async def test_init_create_all(database):
    async with database.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
