import enum
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, DateTime, Column, Enum, BigInteger, Integer

__all__ = (
    "User",
    "UserDataBase",
    "PermissionsEnum",
)


class PermissionsEnum(int, enum.Enum):
    OWNER = 1
    ADMIN = 2
    PUBLIC = 3


class User(SQLModel):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")
    id: Optional[int] = Field(
        default=None, primary_key=True, sa_column=Column(Integer(), primary_key=True, autoincrement=True)
    )
    user_id: int = Field(unique=True, sa_column=Column(BigInteger()))
    permissions: Optional[PermissionsEnum] = Field(sa_column=Column(Enum(PermissionsEnum)))
    locale: Optional[str] = Field()
    ban_end_time: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True)))
    ban_start_time: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True)))
    is_banned: Optional[int] = Field()


class UserDataBase(User, table=True):
    __tablename__ = "users"
