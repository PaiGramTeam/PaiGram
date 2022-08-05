from typing import Optional

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field()
    yuanshen_uid: int = Field()
    genshin_uid: int = Field()
    region: int = Field()
