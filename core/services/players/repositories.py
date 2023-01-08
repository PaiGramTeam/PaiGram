from typing import Optional, List
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.dependence.mysql import MySQL
from core.services.players.models import PlayersDataBase as Player, RegionEnum

__all__ = ("PlayersRepository",)


class PlayersRepository:
    def __init__(self, mysql: MySQL):
        self.engine = mysql.engine

    async def get_by_user_id(self, user_id: int, region: Optional[RegionEnum]) -> Optional[Player]:
        async with AsyncSession(self.engine) as session:
            if region:
                statement = select(Player).where(
                    Player.user_id == user_id and Player.region == region and Player.is_chosen == 1
                )
            else:
                statement = select(Player).where(Player.user_id == user_id and Player.is_chosen == 1)
            results = await session.exec(statement)
            return results.first()

    async def add(self, player: Player):
        async with AsyncSession(self.engine) as session:
            session.add(player)
            await session.commit()

    async def remove(self, player: Player):
        async with AsyncSession(self.engine) as session:
            await session.delete(player)
            await session.commit()

    async def get_all_by_user_id(self, user_id: int) -> List[Player]:
        async with AsyncSession(self.engine) as session:
            statement = select(Player).where(Player.user_id == user_id)
            results = await session.exec(statement)
            players = results.all()
            return players
