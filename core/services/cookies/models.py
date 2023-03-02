import enum
from typing import Optional, Dict

from sqlmodel import SQLModel, Field, Boolean, Column, Enum, JSON

from core.services.players.models import RegionEnum

__all__ = ("Cookies", "CookiesDataBase", "CookiesStatusEnum")


class CookiesStatusEnum(int, enum.Enum):
    STATUS_SUCCESS = 0
    INVALID_COOKIES = 1
    TOO_MANY_REQUESTS = 2


class Cookies(SQLModel):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")
    id: int = Field(primary_key=True)
    user_id: int = Field()
    account_id: int = Field()
    data: Optional[Dict[str, str]] = Field(sa_column=Column(JSON))
    status: CookiesStatusEnum = Field(sa_column=Column(Enum(CookiesStatusEnum)))
    region: RegionEnum = Field(sa_column=Column(Enum(RegionEnum)))
    is_share: Optional[bool] = Field(sa_column=Column(Boolean))


class CookiesDataBase(Cookies, table=True):
    __tablename__ = "cookies"
