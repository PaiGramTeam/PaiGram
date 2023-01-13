import enum
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, DateTime, Column, Enum

__all__ = (
    "User",
    "UserDataBase",
    "PermissionsEnum",
)


class PermissionsEnum(int, enum.Enum):
    NULL = 0
    ADMIN = 1
    PUBLIC = 2


class User(SQLModel):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")
    id: int = Field(primary_key=True)
    user_id: int = Field(unique=True)
    permissions: PermissionsEnum = Field(sa_column=Column(Enum(PermissionsEnum)))
    locale: Optional[str] = Field()
    ban_end_time: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True)))
    ban_start_time: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True)))
    is_banned: Optional[int] = Field()


class UserDataBase(User, table=True):
    __tablename__ = "users"
