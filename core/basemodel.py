import enum

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib

from pydantic import BaseSettings

__all__ = ("RegionEnum", "Settings")


class RegionEnum(int, enum.Enum):
    """账号数据所在服务器"""

    NULL = 0
    HYPERION = 1  # 米忽悠国服 hyperion
    HOYOLAB = 2  # 米忽悠国际服 hoyolab


class Settings(BaseSettings):
    def __new__(cls, *args, **kwargs):
        cls.update_forward_refs()
        return super(Settings, cls).__new__(cls)  # pylint: disable=E1120

    class Config(BaseSettings.Config):
        case_sensitive = False
        json_loads = jsonlib.loads
        json_dumps = jsonlib.dumps
