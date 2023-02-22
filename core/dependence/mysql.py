import contextlib
from typing import Optional

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from typing_extensions import Self

from core.base_service import BaseService
from core.config import ApplicationConfig
from core.sqlmodel.session import AsyncSession

__all__ = ("MySQL",)


class MySQL(BaseService.Dependence):
    @classmethod
    def from_config(cls, config: ApplicationConfig) -> Self:
        return cls(**config.mysql.dict())

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.database = database
        self.password = password
        self.username = username
        self.port = port
        self.host = host
        self.url = URL.create(
            "mysql+asyncmy",
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )
        self.engine = create_async_engine(self.url)
        self.Session = sessionmaker(bind=self.engine, class_=AsyncSession)

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncSession:
        yield self.Session()

    async def shutdown(self):
        self.Session.close_all()
