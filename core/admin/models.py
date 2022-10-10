from sqlmodel import SQLModel, Field


class Admin(SQLModel, table=True):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")

    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.user_id")
