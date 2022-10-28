from enum import Enum
from pathlib import Path
from typing import (
    List,
    Optional,
    Union,
)

import dotenv
from pydantic import (
    AnyUrl,
    BaseModel,
    Field,
    validator,
)

from utils.const import PROJECT_ROOT
from utils.models.base import Settings

__all__ = ["BotConfig", "config", "JoinGroups"]

dotenv.load_dotenv()


class JoinGroups(str, Enum):
    NO_ALLOW = "NO_ALLOW"
    ALLOW_AUTH_USER = "ALLOW_AUTH_USER"
    ALLOW_ALL = "ALLOW_ALL"


class ConfigChannel(BaseModel):
    name: str
    chat_id: int


class ConfigUser(BaseModel):
    username: Optional[str]
    user_id: int


class MySqlConfig(Settings):
    host: str = "127.0.0.1"
    port: int = 3306
    username: str
    password: str
    database: str

    class Config(Settings.Config):
        env_prefix = "db_"


class RedisConfig(Settings):
    host: str = "127.0.0.1"
    port: int = 6379
    database: int = Field(env='redis_db')

    class Config(Settings.Config):
        env_prefix = "redis_"


class LoggerConfig(Settings):
    name: str = "TGPaimon"
    width: int = 180
    time_format: str = "[%Y-%m-%d %X]"
    traceback_max_frames: int = 20
    path: Path = PROJECT_ROOT / "logs"
    render_keywords: List[str] = ["BOT"]
    locals_max_length: int = 10
    locals_max_string: int = 80
    locals_max_depth: Optional[int] = None
    filtered_names: List[str] = ["uvicorn"]

    @validator("locals_max_depth", pre=True, check_fields=False)
    def locals_max_depth_validator(cls, value) -> Optional[int]:  # pylint: disable=R0201
        if int(value) <= 0:
            return None
        return value

    class Config(Settings.Config):
        env_prefix = "logger_"


class MTProtoConfig(Settings):
    api_id: Optional[int] = None
    api_hash: Optional[str] = None


class WebServerConfig(Settings):
    url: AnyUrl = "http://localhost:8080"
    host: str = "localhost"
    port: int = 8080

    class Config(Settings.Config):
        env_prefix = "web_"


class BotConfig(Settings):
    debug: bool = False

    bot_token: str = ""

    error_notification_chat_id: Optional[str] = None

    channels: List["ConfigChannel"] = []
    admins: List["ConfigUser"] = []
    verify_groups: List[Union[int, str]] = []
    join_groups: Optional[JoinGroups] = JoinGroups.NO_ALLOW

    timeout: int = 10
    read_timeout: float = 2
    write_timeout: Optional[float] = None
    connect_timeout: Optional[float] = None
    pool_timeout: Optional[float] = None

    genshin_ttl: Optional[int] = None

    enka_network_api_agent: str = ""
    pass_challenge_api: str = ""
    pass_challenge_app_key: str = ""

    error_pb_url: str = ""
    error_pb_sunset: int = 43200
    error_pb_max_lines: int = 1000
    error_sentry_dsn: str = ""

    mysql: MySqlConfig = MySqlConfig()
    logger: LoggerConfig = LoggerConfig()
    webserver: WebServerConfig = WebServerConfig()
    redis: RedisConfig = RedisConfig()
    mtproto: MTProtoConfig = MTProtoConfig()


BotConfig.update_forward_refs()
config = BotConfig()


def main():
    print(config.redis.database)


if __name__ == '__main__':
    main()
