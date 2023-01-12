from typing import List, Optional

from core.base_service import BaseService
from core.services.players.models import PlayersDataBase as Player, RegionEnum
from core.services.players.repositories import PlayersRepository

__all__ = ("PlayersService",)


class PlayersService(BaseService):
    def __init__(self, players_repository: PlayersRepository) -> None:
        self._repository = players_repository

    async def get_player_by_user_id(self, user_id: int, region: Optional[RegionEnum]) -> Optional[Player]:
        """从数据库获取用户信息
        :param user_id:用户ID
        :param region:
        :return: Return player info
        """
        return await self._repository.get_by_user_id(user_id, region)

    async def add(self, player: Player) -> None:
        await self._repository.add(player)

    async def update(self, player: Player) -> None:
        await self._repository.update(player)

    async def get_all_by_user_id(self, user_id: int) -> List[Player]:
        return await self._repository.get_all_by_user_id(user_id)

    async def remove_all_by_user_id(self, user_id: int):
        players = await self._repository.get_all_by_user_id(user_id)
        for player in players:
            await self._repository.remove(player)
