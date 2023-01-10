import pytest_asyncio


from core.config import config
from core.dependence.mysql import MySQL


@pytest_asyncio.fixture(scope="session")
def mysql():
    _mysql = MySQL.from_config(config=config)
    return _mysql
