from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from typing_extensions import Self

from core.config import AppConfig
from core.service import Service
from utils.log import logger


class MySQL(Service):
    @classmethod
    def from_config(cls, config: AppConfig) -> Self:
        return cls(**config.mysql.dict())

    def __init__(self, host: str = "127.0.0.1", port: int = 3306, username: str = "root",
                 password: str = "", database: str = ""):
        self.database = database
        self.password = password
        self.user = username
        self.port = port
        self.host = host
        logger.debug(f'获取数据库配置 [host]: {self.host}')
        logger.debug(f'获取数据库配置 [port]: {self.port}')
        logger.debug(f'获取数据库配置 [user]: {self.user}')
        logger.debug(f'获取数据库配置 [password][len]: {len(self.password)}')
        logger.debug(f'获取数据库配置 [db]: {self.database}')
        self.engine = create_async_engine(
            f"mysql+asyncmy://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        )
        self.Session = sessionmaker(bind=self.engine, class_=AsyncSession)

    async def start(self, *args, **kwargs):
        pass

    async def stop(self, *args, **kwargs):
        pass

    async def get_session(self):
        """获取会话"""
        async with self.Session() as session:
            yield session

    async def wait_closed(self):
        pass
