import datetime

from typing import Any, List

from genshin.models import BaseTransaction
from pydantic import BaseModel, BaseConfig

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib


class _ModelConfig(BaseConfig):
    json_dumps = jsonlib.dumps
    json_loads = jsonlib.loads


class BaseInfo(BaseModel):
    Config = _ModelConfig
    uid: str = "0"
    lang: str = "zh-cn"
    export_time: str = ""
    export_timestamp: int = 0
    export_app: str = "PaimonBot"

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.export_time:
            self.update_now()

    def update_now(self):
        self.export_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.export_timestamp = int(datetime.datetime.now().timestamp())


class PayLog(BaseModel):
    Config = _ModelConfig
    info: BaseInfo
    list: List[BaseTransaction]
