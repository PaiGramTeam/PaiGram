from pathlib import Path
from typing import (
    List,
    Optional,
    Union,
)

import dotenv
import ujson as json
from pydantic import (
    BaseModel,
    BaseSettings,
)

__all__ = ['BotConfig', 'config']

from utils.const import PROJECT_ROOT

dotenv.load_dotenv()


class BotConfig(BaseSettings):
    debug: bool = False

    db_host: str
    db_port: int
    db_username: str
    db_password: str
    db_database: str

    redis_host: str
    redis_port: int
    redis_db: int

    bot_token: str
    error_notification_chat_id: str

    api_id: Optional[int]
    api_hash: Optional[str]

    channels: List['ConfigChannel'] = []
    admins: List['ConfigUser'] = []
    verify_groups: List[Union[int, str]] = []

    logger_width: int = 180
    logger_log_path: str = './logs'
    logger_time_format: str = "[%Y-%m-%d %X]"
    logger_traceback_max_frames: int = 20
    logger_render_keywords: List[str] = ['BOT']

    enka_network_api_agent: str = ""

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
        )

    @property
    def mtproto(self) -> "MTProtoConfig":
        return MTProtoConfig(
            api_id=self.api_id,
            api_hash=self.api_hash,
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
    host: str = '127.0.0.1'
    port: int
    database: int = 0


class LoggerConfig(BaseModel):
    width: int = 180
    time_format: str = "[%Y-%m-%d %X]"
    traceback_max_frames: int = 20
    path: Path = PROJECT_ROOT / 'logs'
    render_keywords: List[str] = ['BOT']


class MTProtoConfig(BaseModel):
    api_id: Optional[int]
    api_hash: Optional[str]


BotConfig.update_forward_refs()
config = BotConfig()
