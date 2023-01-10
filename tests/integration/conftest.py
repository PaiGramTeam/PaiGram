import asyncio

import pytest
import pytest_asyncio

from core.config import config
from core.dependence.mysql import MySQL


@pytest_asyncio.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    res = policy.new_event_loop()
    asyncio.set_event_loop(res)
    yield res
    res.close()


@pytest.fixture(scope="session")
def mysql():
    _mysql = MySQL.from_config(config=config)
    return _mysql
