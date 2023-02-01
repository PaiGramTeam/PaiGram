from typing import List, Optional

from core.base_service import BaseService
from core.services.players.models import PlayersDataBase as Player, RegionEnum
from core.services.players.repositories import PlayersRepository

__all__ = ("PlayersService",)


class PlayersService(BaseService):
    def __init__(self, players_repository: PlayersRepository) -> None:
        self._repository = players_repository

    async def get(
        self,
        user_id: int,
        player_id: Optional[int] = None,
        account_id: Optional[int] = None,
        region: Optional[RegionEnum] = None,
        is_chosen: Optional[bool] = None,
    ) -> Optional[Player]:
        return await self._repository.get(user_id, player_id, account_id, region, is_chosen)

    async def get_player(self, user_id: int, region: Optional[RegionEnum] = None) -> Optional[Player]:
        return await self._repository.get(user_id, region=region, is_chosen=True)

    async def add(self, player: Player) -> None:
        await self._repository.add(player)

    async def update(self, player: Player) -> None:
        await self._repository.update(player)

    async def get_all_by_user_id(self, user_id: int) -> List[Player]:
        return await self._repository.get_all_by_user_id(user_id)

    async def remove_all_by_user_id(self, user_id: int):
        players = await self._repository.get_all_by_user_id(user_id)
        for player in players:
            await self._repository.delete(player)

    async def delete(self, player: Player):
        await self._repository.delete(player)
