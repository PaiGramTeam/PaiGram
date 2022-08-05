from typing import Optional

from sqlmodel import SQLModel, Field, Enum, Column

from models.base import RegionEnum


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field()
    yuanshen_uid: int = Field()
    genshin_uid: int = Field()
    region: Optional[RegionEnum] = Field(sa_column=Column(Enum(RegionEnum)))
