import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import func, BigInteger
from sqlmodel import Column, DateTime, Enum, Field, SQLModel, Integer

__all__ = ("SignStatusEnum", "Sign")


class SignStatusEnum(int, enum.Enum):
    STATUS_SUCCESS = 0  # 签到成功
    INVALID_COOKIES = 1  # Cookie无效
    ALREADY_CLAIMED = 2  # 已经获取奖励
    NEED_CHALLENGE = 3  # 需要验证码
    GENSHIN_EXCEPTION = 4  # API异常
    TIMEOUT_ERROR = 5  # 请求超时
    BAD_REQUEST = 6  # 请求失败
    FORBIDDEN = 7  # 这错误一般为通知失败 机器人被用户BAN


class Sign(SQLModel, table=True):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")
    id: Optional[int] = Field(
        default=None, primary_key=True, sa_column=Column(Integer(), primary_key=True, autoincrement=True)
    )
    user_id: int = Field(primary_key=True, sa_column=Column(BigInteger(), index=True))
    chat_id: Optional[int] = Field(default=None)
    time_created: Optional[datetime] = Field(
        sa_column=Column(DateTime, server_default=func.now())  # pylint: disable=E1102
    )
    time_updated: Optional[datetime] = Field(sa_column=Column(DateTime, onupdate=func.now()))  # pylint: disable=E1102
    status: Optional[SignStatusEnum] = Field(sa_column=Column(Enum(SignStatusEnum)))
