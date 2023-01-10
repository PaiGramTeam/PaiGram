import logging

import pytest

logger = logging.getLogger("MySQL")


# noinspection PyShadowingNames
@pytest.mark.asyncio
async def test_mysql(mysql):
    assert mysql
