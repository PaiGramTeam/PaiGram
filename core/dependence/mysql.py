import contextlib

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from typing_extensions import Self

from core.base_service import BaseService
from core.config import BotConfig
from core.sqlmodel.session import AsyncSession

__all__ = ("MySQL",)


class MySQL(BaseService.Dependence):
    @classmethod
    def from_config(cls, config: BotConfig) -> Self:
        return cls(**config.mysql.dict())

    def __init__(self, host: str, port: int, username: str, password: str, database: str):
        self.database = database
        self.password = password
        self.user = username
        self.port = port
        self.host = host
        self.url = f"mysql+asyncmy://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        self.engine = create_async_engine(self.url)
        self.Session = sessionmaker(bind=self.engine, class_=AsyncSession)

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncSession:
        yield self.Session()

    async def shutdown(self):
        self.Session.close_all()
