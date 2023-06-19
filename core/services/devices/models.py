from typing import Optional

from sqlmodel import SQLModel, Field, Column, Integer, BigInteger

__all__ = ("Devices", "DevicesDataBase")


class Devices(SQLModel):
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")
    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    account_id: int = Field(
        default=None,
        sa_column=Column(
            BigInteger(),
        ),
    )
    device_id: str = Field()
    device_fp: str = Field()
    device_name: Optional[str] = Field(default=None)


class DevicesDataBase(Devices, table=True):
    __tablename__ = "devices"
