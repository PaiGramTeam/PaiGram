from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

import dotenv
from pydantic import AnyUrl, Field

from core.basemodel import Settings
from utils.const import PROJECT_ROOT
from utils.typedefs import NaturalNumber

__all__ = ("ApplicationConfig", "config", "JoinGroups")

dotenv.load_dotenv()


class JoinGroups(str, Enum):
    NO_ALLOW = "NO_ALLOW"
    ALLOW_AUTH_USER = "ALLOW_AUTH_USER"
    ALLOW_USER = "ALLOW_USER"
    ALLOW_ALL = "ALLOW_ALL"


class DatabaseConfig(Settings):
    driver_name: str = "mysql+asyncmy"
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None

    class Config(Settings.Config):
        env_prefix = "db_"


class RedisConfig(Settings):
    host: str = "127.0.0.1"
    port: int = 6379
    database: int = Field(default=0, env="redis_db")
    password: Optional[str] = None

    class Config(Settings.Config):
        env_prefix = "redis_"


class LoggerConfig(Settings):
    name: str = "PaiGram"
    width: Optional[int] = None
    time_format: str = "[%Y-%m-%d %X]"
    traceback_max_frames: int = 20
    path: Path = PROJECT_ROOT / "logs"
    render_keywords: List[str] = ["BOT"]
    locals_max_length: int = 10
    locals_max_string: int = 80
    locals_max_depth: Optional[NaturalNumber] = None
    filtered_names: List[str] = ["uvicorn"]

    class Config(Settings.Config):
        env_prefix = "logger_"


class MTProtoConfig(Settings):
    api_id: Optional[int] = None
    api_hash: Optional[str] = None


class WebServerConfig(Settings):
    enable: bool = False
    """是否启用WebServer"""

    url: AnyUrl = "http://localhost:8080"
    host: str = "localhost"
    port: int = 8080

    class Config(Settings.Config):
        env_prefix = "web_"


class ErrorConfig(Settings):
    pb_url: str = ""
    pb_sunset: int = 43200
    pb_max_lines: int = 1000
    sentry_dsn: str = ""
    notification_chat_id: Optional[str] = None

    class Config(Settings.Config):
        env_prefix = "error_"


class ReloadConfig(Settings):
    delay: float = 0.25
    dirs: List[str] = []
    include: List[str] = []
    exclude: List[str] = []

    class Config(Settings.Config):
        env_prefix = "reload_"


class NoticeConfig(Settings):
    user_mismatch: str = "再乱点我叫西风骑士团、千岩军、天领奉行、三十人团和风纪官了！"

    class Config(Settings.Config):
        env_prefix = "notice_"


class ApplicationConfig(Settings):
    debug: bool = False
    """debug 开关"""
    retry: int = 5
    """重试次数"""
    auto_reload: bool = False
    """自动重载"""

    proxy_url: Optional[AnyUrl] = None
    """代理链接"""

    bot_token: str = ""
    """BOT的token"""

    owner: Optional[int] = None

    channels: List[int] = []
    """文章推送群组"""

    verify_groups: List[Union[int, str]] = []
    """启用群验证功能的群组"""
    join_groups: Optional[JoinGroups] = JoinGroups.NO_ALLOW
    """是否允许机器人被邀请到其它群组"""

    timeout: int = 10
    connection_pool_size: int = 256
    read_timeout: Optional[float] = None
    write_timeout: Optional[float] = None
    connect_timeout: Optional[float] = None
    pool_timeout: Optional[float] = None
    update_read_timeout: Optional[float] = None
    update_write_timeout: Optional[float] = None
    update_connect_timeout: Optional[float] = None
    update_pool_timeout: Optional[float] = None

    genshin_ttl: Optional[int] = None

    enka_network_api_agent: str = ""
    pass_challenge_api: str = ""
    pass_challenge_app_key: str = ""
    pass_challenge_user_web: str = ""

    reload: ReloadConfig = ReloadConfig()
    database: DatabaseConfig = DatabaseConfig()
    logger: LoggerConfig = LoggerConfig()
    webserver: WebServerConfig = WebServerConfig()
    redis: RedisConfig = RedisConfig()
    mtproto: MTProtoConfig = MTProtoConfig()
    error: ErrorConfig = ErrorConfig()
    notice: NoticeConfig = NoticeConfig()


ApplicationConfig.update_forward_refs()
config = ApplicationConfig()
