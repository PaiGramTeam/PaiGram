from datetime import datetime
from typing import Optional

from pydantic import BaseModel, BaseSettings
from sqlalchemy import TypeDecorator
from sqlmodel import Boolean, Column, Enum, Field, SQLModel, Integer, Index, BigInteger, VARCHAR, func, DateTime

from core.basemodel import RegionEnum

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib

__all__ = ("Player", "PlayersDataBase", "PlayerInfo", "PlayerInfoSQLModel")


class Player(SQLModel):
    __table_args__ = (
        Index("index_user_account_player", "user_id", "account_id", "player_id", unique=True),
        dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci"),
    )
    id: Optional[int] = Field(
        default=None, primary_key=True, sa_column=Column(Integer(), primary_key=True, autoincrement=True)
    )
    user_id: int = Field(primary_key=True, sa_column=Column(BigInteger()))
    account_id: int = Field(default=None, primary_key=True, sa_column=Column(BigInteger()))
    player_id: int = Field(primary_key=True, sa_column=Column(BigInteger()))
    region: RegionEnum = Field(sa_column=Column(Enum(RegionEnum)))
    is_chosen: Optional[bool] = Field(sa_column=Column(Boolean))


class PlayersDataBase(Player, table=True):
    __tablename__ = "players"


class ExtraPlayerInfo(BaseModel):
    class Config(BaseSettings.Config):
        json_loads = jsonlib.loads
        json_dumps = jsonlib.dumps

    waifu_id: Optional[int] = None


class ExtraPlayerType(TypeDecorator):  # pylint: disable=W0223
    impl = VARCHAR(length=521)

    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        :param value: ExtraPlayerInfo | obj | None
        :param dialect:
        :return:
        """
        if value is not None:
            if isinstance(value, ExtraPlayerInfo):
                return value.json()
            raise TypeError
        return value

    def process_result_value(self, value, dialect):
        """
        :param value: str | obj | None
        :param dialect:
        :return:
        """
        if value is not None:
            return ExtraPlayerInfo.parse_raw(value)
        return None


class PlayerInfo(SQLModel):
    __table_args__ = (
        Index("index_user_account_player", "user_id", "player_id", unique=True),
        dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci"),
    )
    id: Optional[int] = Field(
        default=None, primary_key=True, sa_column=Column(Integer(), primary_key=True, autoincrement=True)
    )
    user_id: int = Field(primary_key=True, sa_column=Column(BigInteger()))
    player_id: int = Field(primary_key=True, sa_column=Column(BigInteger()))
    nickname: Optional[str] = Field()
    signature: Optional[str] = Field()
    hand_image: Optional[int] = Field()
    name_card: Optional[int] = Field()
    extra_data: Optional[ExtraPlayerInfo] = Field(sa_column=Column(ExtraPlayerType))
    create_time: Optional[datetime] = Field(
        sa_column=Column(DateTime, server_default=func.now())  # pylint: disable=E1102
    )
    last_save_time: Optional[datetime] = Field(sa_column=Column(DateTime, onupdate=func.now()))  # pylint: disable=E1102
    is_update: Optional[bool] = Field(sa_column=Column(Boolean))


class PlayerInfoSQLModel(PlayerInfo, table=True):
    __tablename__ = "players_info"
