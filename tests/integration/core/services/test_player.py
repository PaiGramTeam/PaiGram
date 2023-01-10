import logging

import pytest
import pytest_asyncio
from sqlmodel import SQLModel

from core.config import config
from core.dependence.mysql import MySQL
from core.services.players import PlayersService
from core.services.players.models import PlayersDataBase, RegionEnum
from core.services.players.repositories import PlayersRepository

logger = logging.getLogger("PlayersService")

data = PlayersDataBase(
    user_id=1,
    account_id=2,
    player_id=3,
    nickname="nickname",
    signature="signature",
    hand_image=4,
    name_card_id=5,
    waifu_id=6,
    region=RegionEnum.HYPERION,
    is_chosen=1,
)


@pytest_asyncio.fixture()
async def mysql():
    _mysql = MySQL.from_config(config=config)
    logger.info("URL :%s", _mysql.url)
    return _mysql


# noinspection PyShadowingNames
@pytest_asyncio.fixture()
def service(mysql):
    repository = PlayersRepository(mysql)
    return PlayersService(repository)


# noinspection PyShadowingNames
@pytest.mark.asyncio
async def test_init_models(mysql):
    async with mysql.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)


# noinspection PyShadowingNames
@pytest.mark.asyncio
async def test_add_player(service):
    await service.add(data)
