import asyncio

import pytest
import pytest_asyncio

from core.config import config
from core.dependence.mysql import MySQL
from core.dependence.redisdb import RedisDB


@pytest_asyncio.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    res = policy.new_event_loop()
    asyncio.set_event_loop(res)
    yield res
    res.close()


@pytest.fixture(scope="session")
def mysql():
    return MySQL.from_config(config=config)


@pytest.fixture(scope="session")
def redis():
    return RedisDB.from_config(config=config)
