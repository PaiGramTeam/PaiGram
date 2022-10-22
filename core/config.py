from enum import Enum
from pathlib import Path
from typing import (
    List,
    Optional,
    Union,
)

import dotenv
import ujson as json
from pydantic import BaseModel, BaseSettings, validator

from utils.const import PROJECT_ROOT

__all__ = ["BotConfig", "config", "JoinGroups"]

dotenv.load_dotenv()


class JoinGroups(str, Enum):
    NO_ALLOW = "NO_ALLOW"
    ALLOW_AUTH_USER = "ALLOW_AUTH_USER"
    ALLOW_ALL = "ALLOW_ALL"


class BotConfig(BaseSettings):
    debug: bool = False

    db_host: str = ""
    db_port: int = 0
    db_username: str = ""
    db_password: str = ""
    db_database: str = ""

    redis_host: str = ""
    redis_port: int = 0
    redis_db: int = 0

    bot_token: str = ""

    error_notification_chat_id: Optional[str] = None

    api_id: Optional[int] = None
    api_hash: Optional[str] = None

    channels: List["ConfigChannel"] = []
    admins: List["ConfigUser"] = []
    verify_groups: List[Union[int, str]] = []
    join_groups: Optional[JoinGroups] = JoinGroups.NO_ALLOW

    logger_width: int = 180
    logger_log_path: str = "./logs"
    logger_time_format: str = "[%Y-%m-%d %X]"
    logger_traceback_max_frames: int = 20
    logger_render_keywords: List[str] = ["BOT"]
    logger_locals_max_depth: Optional[int] = 0
    logger_locals_max_length: int = 10
    logger_locals_max_string: int = 80

    timeout: int = 10
    read_timeout: float = 2
    write_timeout: Optional[float] = None
    connect_timeout: Optional[float] = None
    pool_timeout: Optional[float] = None

    genshin_ttl: Optional[int] = None

    enka_network_api_agent: str = ""
    pass_challenge_api: str = ""
    pass_challenge_app_key: str = ""

    web_url: str = "http://localhost:8080/"
    web_host: str = "localhost"
    web_port: int = 8080

    error_pb_url: str = ""
    error_pb_sunset: int = 43200
    error_pb_max_lines: int = 1000
    error_sentry_dsn: str = ""

    class Config:
        case_sensitive = False
        json_loads = json.loads
        json_dumps = json.dumps

    @property
    def mysql(self) -> "MySqlConfig":
        return MySqlConfig(
            host=self.db_host,
            port=self.db_port,
            username=self.db_username,
            password=self.db_password,
            database=self.db_database,
        )

    @property
    def redis(self) -> "RedisConfig":
        return RedisConfig(
            host=self.redis_host,
            port=self.redis_port,
            database=self.redis_db,
        )

    @property
    def logger(self) -> "LoggerConfig":
        return LoggerConfig(
            width=self.logger_width,
            traceback_max_frames=self.logger_traceback_max_frames,
            path=PROJECT_ROOT.joinpath(self.logger_log_path).resolve(),
            time_format=self.logger_time_format,
            render_keywords=self.logger_render_keywords,
            locals_max_length=self.logger_locals_max_length,
            locals_max_string=self.logger_locals_max_string,
            locals_max_depth=self.logger_locals_max_depth,
        )

    @property
    def mtproto(self) -> "MTProtoConfig":
        return MTProtoConfig(
            api_id=self.api_id,
            api_hash=self.api_hash,
        )

    @property
    def webserver(self) -> "WebServerConfig":
        return WebServerConfig(
            host=self.web_host,
            port=self.web_port,
        )


class ConfigChannel(BaseModel):
    name: str
    chat_id: int


class ConfigUser(BaseModel):
    username: Optional[str]
    user_id: int


class MySqlConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3306
    username: str
    password: str
    database: str


class RedisConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int
    database: int = 0


class LoggerConfig(BaseModel):
    width: int = 180
    time_format: str = "[%Y-%m-%d %X]"
    traceback_max_frames: int = 20
    path: Path = PROJECT_ROOT / "logs"
    render_keywords: List[str] = ["BOT"]
    locals_max_length: int = 10
    locals_max_string: int = 80
    locals_max_depth: Optional[int] = None

    @validator("locals_max_depth", pre=True, check_fields=False)
    def locals_max_depth_validator(cls, value) -> Optional[int]:  # pylint: disable=R0201
        if value <= 0:
            return None
        return value


class MTProtoConfig(BaseModel):
    api_id: Optional[int]
    api_hash: Optional[str]


class WebServerConfig(BaseModel):
    host: Optional[str]
    port: Optional[int]


BotConfig.update_forward_refs()
config = BotConfig()
