from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from logger import Log


class MySQL:
    def __init__(self, host: str = "127.0.0.1", port: int = 3306, user: str = "root",
                 password: str = "", database: str = ""):
        self.database = database
        self.password = password
        self.user = user
        self.port = port
        self.host = host
        Log.debug(f'获取数据库配置 [host]: {self.host}')
        Log.debug(f'获取数据库配置 [port]: {self.port}')
        Log.debug(f'获取数据库配置 [user]: {self.user}')
        Log.debug(f'获取数据库配置 [password][len]: {len(self.password)}')
        Log.debug(f'获取数据库配置 [db]: {self.database}')
        self.engine = create_async_engine(f"mysql+asyncmy://{user}:{password}@{host}:{port}/{database}")
        self.Session = sessionmaker(bind=self.engine, class_=AsyncSession)

    async def get_session(self):
        """获取会话"""
        async with self.Session() as session:
            yield session

    async def wait_closed(self):
        pass
