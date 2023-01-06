import enum
from typing import Dict, Optional

from core.service import Component
from sqlmodel import Column, Enum, Field, JSON, SQLModel

__all__ = ["Cookies", "CookiesStatusEnum", "HyperionCookie", "HoyolabCookie"]


class CookiesStatusEnum(Component, int, enum.Enum):
    STATUS_SUCCESS = 0
    INVALID_COOKIES = 1
    TOO_MANY_REQUESTS = 2


class Cookies(Component, SQLModel):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")

    id: int = Field(primary_key=True)
    user_id: Optional[int] = Field(foreign_key="user.user_id")
    cookies: Optional[Dict[str, str]] = Field(sa_column=Column(JSON))
    status: Optional[CookiesStatusEnum] = Field(sa_column=Column(Enum(CookiesStatusEnum)))


class HyperionCookie(Cookies, table=True):
    __tablename__ = "mihoyo_cookies"


class HoyolabCookie(Cookies, table=True):
    __tablename__ = "hoyoverse_cookies"
