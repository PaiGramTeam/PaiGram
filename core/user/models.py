from typing import Optional

from sqlmodel import SQLModel, Field, Enum, Column

from models.base import RegionEnum


class User(SQLModel, table=True):
    __table_args__ = dict(mysql_charset='utf8mb4', mysql_collate="utf8mb4_general_ci")

    id: int = Field(primary_key=True)
    user_id: int = Field(unique=True)
    yuanshen_uid: Optional[int] = Field()
    genshin_uid: Optional[int] = Field()
    region: Optional[RegionEnum] = Field(sa_column=Column(Enum(RegionEnum)))
