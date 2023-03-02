from typing import List, Optional

from sqlmodel import select

from core.base_service import BaseService
from core.dependence.mysql import MySQL
from core.services.players.models import PlayersDataBase as Player, RegionEnum
from core.sqlmodel.session import AsyncSession

__all__ = ("PlayersRepository",)


class PlayersRepository(BaseService.Component):
    def __init__(self, mysql: MySQL):
        self.engine = mysql.engine

    async def get(
        self,
        user_id: int,
        player_id: Optional[int] = None,
        account_id: Optional[int] = None,
        region: Optional[RegionEnum] = None,
        is_chosen: Optional[bool] = None,
    ) -> Optional[Player]:
        async with AsyncSession(self.engine) as session:
            statement = select(Player).where(Player.user_id == user_id)
            if player_id is not None:
                statement = statement.where(Player.player_id == player_id)
            if account_id is not None:
                statement = statement.where(Player.account_id == account_id)
            if region is not None:
                statement = statement.where(Player.region == region)
            if is_chosen is not None:
                statement = statement.where(Player.is_chosen == is_chosen)
            results = await session.exec(statement)
            return results.first()

    async def add(self, player: Player) -> None:
        async with AsyncSession(self.engine) as session:
            session.add(player)
            await session.commit()

    async def delete(self, player: Player) -> None:
        async with AsyncSession(self.engine) as session:
            await session.delete(player)
            await session.commit()

    async def update(self, player: Player) -> None:
        async with AsyncSession(self.engine) as session:
            session.add(player)
            await session.commit()
            await session.refresh(player)

    async def get_all_by_user_id(self, user_id: int) -> List[Player]:
        async with AsyncSession(self.engine) as session:
            statement = select(Player).where(Player.user_id == user_id)
            results = await session.exec(statement)
            players = results.all()
            return players