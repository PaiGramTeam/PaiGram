from datetime import datetime

from pydantic import field_validator, BaseModel

__all__ = ("GachaInfo",)


class GachaInfo(BaseModel):
    begin_time: datetime
    end_time: datetime
    gacha_id: str
    gacha_name: str
    gacha_type: int

    @field_validator("begin_time", "end_time", mode="before")
    @classmethod
    def validate_time(cls, v):
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
