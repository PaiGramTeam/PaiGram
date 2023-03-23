from typing import List, Optional

from sqlmodel import select, delete

from core.base_service import BaseService
from core.basemodel import RegionEnum
from core.dependence.database import Database
from core.services.players.models import PlayerInfoSQLModel
from core.services.players.models import PlayersDataBase as Player
from core.sqlmodel.session import AsyncSession

__all__ = ("PlayersRepository", "PlayerInfoRepository")


class PlayersRepository(BaseService.Component):
    def __init__(self, database: Database):
        self.engine = database.engine

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
            await session.refresh(player)

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


class PlayerInfoRepository(BaseService.Component):
    def __init__(self, database: Database):
        self.engine = database.engine

    async def get(
        self,
        user_id: int,
        player_id: int,
    ) -> Optional[PlayerInfoSQLModel]:
        async with AsyncSession(self.engine) as session:
            statement = (
                select(PlayerInfoSQLModel)
                .where(PlayerInfoSQLModel.player_id == player_id)
                .where(PlayerInfoSQLModel.user_id == user_id)
            )
            results = await session.exec(statement)
            return results.first()

    async def add(self, player: PlayerInfoSQLModel) -> None:
        async with AsyncSession(self.engine) as session:
            session.add(player)
            await session.commit()

    async def delete(self, player: PlayerInfoSQLModel) -> None:
        async with AsyncSession(self.engine) as session:
            await session.delete(player)
            await session.commit()

    async def delete_by_id(
        self,
        user_id: int,
        player_id: int,
    ) -> None:
        async with AsyncSession(self.engine) as session:
            statement = (
                delete(PlayerInfoSQLModel)
                .where(PlayerInfoSQLModel.player_id == player_id)
                .where(PlayerInfoSQLModel.user_id == user_id)
            )
            await session.execute(statement)

    async def update(self, player: PlayerInfoSQLModel) -> None:
        async with AsyncSession(self.engine) as session:
            session.add(player)
            await session.commit()
            await session.refresh(player)
