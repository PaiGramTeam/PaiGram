import enum
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import func, BigInteger, JSON
from sqlmodel import Column, DateTime, Enum, Field, SQLModel, Integer

__all__ = ("Task", "TaskStatusEnum", "TaskTypeEnum")


class TaskStatusEnum(int, enum.Enum):
    STATUS_SUCCESS = 0  # 任务执行成功
    INVALID_COOKIES = 1  # Cookie无效
    ALREADY_CLAIMED = 2  # 已经获取奖励
    NEED_CHALLENGE = 3  # 需要验证码
    GENSHIN_EXCEPTION = 4  # API异常
    TIMEOUT_ERROR = 5  # 请求超时
    BAD_REQUEST = 6  # 请求失败
    FORBIDDEN = 7  # 这错误一般为通知失败 机器人被用户BAN


class TaskTypeEnum(int, enum.Enum):
    SIGN = 0  # 签到
    RESIN = 1  # 体力
    REALM = 2  # 洞天宝钱
    EXPEDITION = 3  # 委托
    TRANSFORMER = 4  # 参量质变仪
    CARD = 5  # 生日画片


class Task(SQLModel, table=True):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")
    id: Optional[int] = Field(
        default=None, primary_key=True, sa_column=Column(Integer(), primary_key=True, autoincrement=True)
    )
    user_id: int = Field(primary_key=True, sa_column=Column(BigInteger(), index=True))
    chat_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger()))
    time_created: Optional[datetime] = Field(
        sa_column=Column(DateTime, server_default=func.now())  # pylint: disable=E1102
    )
    time_updated: Optional[datetime] = Field(sa_column=Column(DateTime, onupdate=func.now()))  # pylint: disable=E1102
    type: TaskTypeEnum = Field(primary_key=True, sa_column=Column(Enum(TaskTypeEnum)))
    status: Optional[TaskStatusEnum] = Field(sa_column=Column(Enum(TaskStatusEnum)))
    data: Optional[Dict[str, Any]] = Field(sa_column=Column(JSON))
