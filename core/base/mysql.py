from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from typing_extensions import Self

from core.config import BotConfig
from core.service import Service


class MySQL(Service):
    @classmethod
    def from_config(cls, config: BotConfig) -> Self:
        return cls(**config.mysql.dict())

    def __init__(self, host: str = "127.0.0.1", port: int = 3306, username: str = "root",  # nosec B107
                 password: str = "", database: str = ""):  # nosec B107
        self.database = database
        self.password = password
        self.user = username
        self.port = port
        self.host = host
        self.engine = create_async_engine(
            f"mysql+asyncmy://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        )
        self.Session = sessionmaker(bind=self.engine, class_=AsyncSession)

    async def get_session(self):
        """获取会话"""
        async with self.Session() as session:
            yield session

    async def stop(self):
        self.Session.close_all()
