import enum
from typing import Optional

from sqlmodel import SQLModel, Field, Boolean, Column, Enum

from core.services.players.models import RegionEnum

__all__ = ("Cookies", "CookiesDataBase", "CookiesStatusEnum")


class CookiesStatusEnum(int, enum.Enum):
    STATUS_SUCCESS = 0
    INVALID_COOKIES = 1
    TOO_MANY_REQUESTS = 2


class Cookies(SQLModel):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")
    id: int = Field(primary_key=True)
    user_id: int = Field(unique=True)
    account_id: int = Field(unique=True)
    data: Optional[str] = Field(unique=True)
    locale: Optional[str] = Field(unique=True)
    status: CookiesStatusEnum = Field(sa_column=Column(Enum(CookiesStatusEnum)))
    region: RegionEnum = Field(sa_column=Column(Enum(RegionEnum)))
    is_share: Optional[bool] = Field(sa_column=Column(Boolean))


class CookiesDataBase(Cookies, table=True):
    __tablename__ = "players"
