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

__all__ = ['BotConfig']

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

    channels: List['ConfigChannel'] = []
    admins: List['ConfigUser'] = []
    verify_groups: List[Union[int, str]] = []

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


BotConfig.update_forward_refs()
