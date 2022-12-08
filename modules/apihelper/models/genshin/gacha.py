from datetime import datetime

from pydantic import BaseModel, validator

__all__ = ("GachaInfo",)


class GachaInfo(BaseModel):
    begin_time: datetime
    end_time: datetime
    gacha_id: str
    gacha_name: str
    gacha_type: int

    @validator("begin_time", "end_time", pre=True, allow_reuse=True)
    def validate_time(cls, v):
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
