from typing import Optional

from sqlmodel import SQLModel, Field


class Admin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field()
