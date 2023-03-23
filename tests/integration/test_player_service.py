import logging

import pytest_asyncio

from core.basemodel import RegionEnum
from core.services.players import PlayersService
from core.services.players.models import PlayersDataBase
from core.services.players.repositories import PlayersRepository

logger = logging.getLogger("TestPlayersService")


@pytest_asyncio.fixture(scope="class", name="players_service")
def service(database):
    repository = PlayersRepository(database)
    _players_service = PlayersService(repository)
    return _players_service


class TestPlayersService:
    @staticmethod
    async def test_add_player(players_service: "PlayersService"):
        data_base = PlayersDataBase(
            user_id=1,
            account_id=2,
            player_id=3,
            region=RegionEnum.HYPERION,
            is_chosen=True,
        )
        await players_service.add(data_base)

    @staticmethod
    async def test_get_player_by_user_id(players_service: "PlayersService"):
        result = await players_service.get(1)
        assert isinstance(result, PlayersDataBase)
        result = await players_service.get(1, region=RegionEnum.HYPERION)
        assert isinstance(result, PlayersDataBase)
        result = await players_service.get(1, region=RegionEnum.HOYOLAB)
        assert not isinstance(result, PlayersDataBase)
        assert result is None

    @staticmethod
    async def test_remove_all_by_user_id(players_service):
        await players_service.remove_all_by_user_id(1)
        result = await players_service.get(1)
        assert not isinstance(result, PlayersDataBase)
        assert result is None

    @staticmethod
    async def test_1(players_service: "PlayersService"):
        """测试 绑定时 账号不存在 账号添加 多账号添加"""
        results = await players_service.get_all_by_user_id(10)
        assert len(results) == 0  # 账号不存在
        data_base = PlayersDataBase(
            user_id=10,
            account_id=2,
            player_id=3,
            region=RegionEnum.HYPERION,
            is_chosen=1,
        )
        await players_service.add(data_base)  # 添加
        result = await players_service.get(10)
        assert result.user_id == 10
        data_base = PlayersDataBase(
            user_id=10,
            account_id=3,
            player_id=3,
            region=RegionEnum.HYPERION,
            is_chosen=True,
        )
        results = await players_service.get_all_by_user_id(10)  # 添加多账号，新的账号设置为主账号
        assert len(results) == 1  # 账号存在只有一个
        for result in results:
            assert result.user_id == 10
            if result.is_chosen == 1:
                result.is_chosen = 0
                await players_service.update(result)
        await players_service.add(data_base)
        results = await players_service.get_all_by_user_id(10)  # check all
        assert len(results) == 2
        for result in results:
            assert result.user_id == 10
            if result.account_id == 3:
                assert result.is_chosen == 1
            if result.account_id == 2:
                assert result.is_chosen == 0
        await players_service.remove_all_by_user_id(10)
        results = await players_service.get_all_by_user_id(10)
        assert len(results) == 0
