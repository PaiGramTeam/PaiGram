import enum
from typing import Optional, Dict

from sqlmodel import SQLModel, Field, Boolean, Column, Enum, JSON, Integer, BigInteger, Index

from core.basemodel import RegionEnum

__all__ = ("Cookies", "CookiesDataBase", "CookiesStatusEnum")


class CookiesStatusEnum(int, enum.Enum):
    STATUS_SUCCESS = 0
    INVALID_COOKIES = 1
    TOO_MANY_REQUESTS = 2


class Cookies(SQLModel):
    __table_args__ = (
        Index("index_user_account", "user_id", "account_id", unique=True),
        dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci"),
    )
    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    user_id: int = Field(
        sa_column=Column(BigInteger()),
    )
    account_id: int = Field(
        default=None,
        sa_column=Column(
            BigInteger(),
        ),
    )
    data: Optional[Dict[str, str]] = Field(sa_column=Column(JSON))
    status: Optional[CookiesStatusEnum] = Field(sa_column=Column(Enum(CookiesStatusEnum)))
    region: RegionEnum = Field(sa_column=Column(Enum(RegionEnum)))
    is_share: Optional[bool] = Field(sa_column=Column(Boolean))


class CookiesDataBase(Cookies, table=True):
    __tablename__ = "cookies"
