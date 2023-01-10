import logging

import pytest_asyncio

from core.services.players import PlayersService
from core.services.players.models import PlayersDataBase, RegionEnum
from core.services.players.repositories import PlayersRepository

logger = logging.getLogger()

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


@pytest_asyncio.fixture(scope="class", name="players_service")
def service(mysql):
    repository = PlayersRepository(mysql)
    _players_service = PlayersService(repository)
    return _players_service


class TestPlayer:
    async def test_add_player(self, players_service):
        await players_service.add(data)

    async def test_get_player_by_user_id(self, players_service):
        result = await players_service.get_player_by_user_id(1, None)
        assert isinstance(result, PlayersDataBase)
        assert result.nickname == "nickname"
        assert result.signature == "signature"
        assert result.waifu_id == 6

    async def test_remove_all_by_user_id(self, players_service):
        await players_service.remove_all_by_user_id(1)
        result = await players_service.get_player_by_user_id(1, None)
        assert not isinstance(result, PlayersDataBase)
        assert result is None
