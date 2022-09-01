import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlmodel import SQLModel, Field, Enum, Column, DateTime


class SignStatusEnum(int, enum.Enum):
    STATUS_SUCCESS = 0  # 签到成功
    INVALID_COOKIES = 1  # Cookie无效
    ALREADY_CLAIMED = 2  # 已经获取奖励
    GENSHIN_EXCEPTION = 3  # API异常
    TIMEOUT_ERROR = 4  # 请求超时
    BAD_REQUEST = 5  # 请求失败
    FORBIDDEN = 6  # 这错误一般为通知失败 机器人被用户BAN


class Sign(SQLModel, table=True):
    __table_args__ = dict(mysql_charset='utf8mb4', mysql_collate="utf8mb4_general_ci")

    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.user_id")
    chat_id: Optional[int] = Field(default=None)
    time_created: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True), server_default=func.now()))
    time_updated: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True), onupdate=func.now()))
    status: Optional[SignStatusEnum] = Field(sa_column=Column(Enum(SignStatusEnum)))
