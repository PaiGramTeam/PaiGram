import enum
from typing import Optional, Dict

from sqlmodel import SQLModel, Field, JSON, Enum, Column


class CookiesStatusEnum(int, enum.Enum):
    STATUS_SUCCESS = 0
    INVALID_COOKIES = 1
    TOO_MANY_REQUESTS = 2


class Cookies(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field()
    cookies: Optional[Dict[str, str]] = Field(sa_column=Column(JSON))
    status: Optional[CookiesStatusEnum] = Field(sa_column=Column(Enum(CookiesStatusEnum)))


class HyperionCookie(Cookies, table=True):
    __tablename__ = 'mihoyo_cookies'


class HoyolabCookie(Cookies, table=True):
    __tablename__ = 'hoyoverse_cookies'
