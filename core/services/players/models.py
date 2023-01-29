import enum
from typing import Optional

from sqlmodel import SQLModel, Field, Enum, Column

__all__ = ("RegionEnum", "Player", "PlayersDataBase")


class RegionEnum(int, enum.Enum):
    """账号数据所在服务器"""

    NULL = 0
    HYPERION = 1  # 米忽悠国服 hyperion
    HOYOLAB = 2  # 米忽悠国际服 hoyolab


class Player(SQLModel):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")
    id: int = Field(primary_key=True)
    user_id: int = Field()
    account_id: int = Field()
    player_id: int = Field()
    nickname: Optional[str] = Field()
    signature: Optional[str] = Field()
    hand_image: Optional[int] = Field()
    name_card_id: Optional[int] = Field()
    waifu_id: Optional[int] = Field()
    region: RegionEnum = Field(sa_column=Column(Enum(RegionEnum)))
    is_chosen: int = Field()


class PlayersDataBase(Player, table=True):
    __tablename__ = "players"