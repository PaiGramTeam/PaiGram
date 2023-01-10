import logging

import pytest
import pytest_asyncio
from sqlmodel import SQLModel

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
def players_service(mysql):
    repository = PlayersRepository(mysql)
    return PlayersService(repository)


@pytest.mark.asyncio
async def test_init_create_all(mysql):
    async with mysql.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)


# noinspection PyShadowingNames
@pytest.mark.asyncio
async def test_add_player(players_service):
    await players_service.add(data)


# noinspection PyShadowingNames
@pytest.mark.asyncio
async def test_get_player_by_user_id(players_service):
    data = await players_service.get_player_by_user_id(1, None)
    assert isinstance(data, PlayersDataBase)
    assert data.nickname == "nickname"
    assert data.signature == "signature"
    assert data.waifu_id == 6


# noinspection PyShadowingNames
@pytest.mark.asyncio
async def test_remove_all_by_user_id(players_service):
    await players_service.remove_all_by_user_id(1)
    data = await players_service.get_player_by_user_id(1, None)
    assert not isinstance(data, PlayersDataBase)
    assert data is None
