from typing import Optional

from sqlmodel import Boolean, Column, Enum, Field, SQLModel, Integer, Index, BigInteger

__all__ = ("Player", "PlayersDataBase")

from core.basemodel import RegionEnum


class Player(SQLModel):
    __table_args__ = (
        Index("index_user_account_player", "user_id", "account_id", "player_id", unique=True),
        dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci"),
    )
    id: Optional[int] = Field(
        default=None, primary_key=True, sa_column=Column(Integer(), primary_key=True, autoincrement=True)
    )
    user_id: int = Field(primary_key=True, sa_column=Column(BigInteger()))
    account_id: int = Field(primary_key=True, sa_column=Column(BigInteger()))
    player_id: int = Field(primary_key=True, sa_column=Column(BigInteger()))
    nickname: Optional[str] = Field()
    signature: Optional[str] = Field()
    hand_image: Optional[int] = Field()
    name_card_id: Optional[int] = Field()
    waifu_id: Optional[int] = Field()
    region: RegionEnum = Field(sa_column=Column(Enum(RegionEnum)))
    is_chosen: Optional[bool] = Field(sa_column=Column(Boolean))


class PlayersDataBase(Player, table=True):
    __tablename__ = "players"
