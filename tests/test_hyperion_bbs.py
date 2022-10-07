"""Test Url
https://bbs.mihoyo.com/ys/article/29023709
"""
import logging

import pytest
import pytest_asyncio
from bs4 import BeautifulSoup
from flaky import flaky

from modules.apihelper.base import PostInfo
from modules.apihelper.hyperion import Hyperion

LOGGER = logging.getLogger(__name__)


@pytest_asyncio.fixture
async def hyperion():
    _hyperion = Hyperion()
    yield _hyperion
    await _hyperion.close()


# noinspection PyShadowingNames
@pytest.mark.asyncio
@flaky(3, 1)
async def test_get_post_info(hyperion):
    post_info = await hyperion.get_post_info(2, 29023709)
    assert post_info
    assert isinstance(post_info, PostInfo)
    assert post_info["post"]["post"]["post_id"] == '29023709'
    assert post_info.post_id == 29023709


# noinspection PyShadowingNames
@pytest.mark.asyncio
@flaky(3, 1)
async def test_get_post_full_info(hyperion):
    post_full_info = await hyperion.get_post_full_info(2, 29023709)
    assert post_full_info
    assert post_full_info["post"]["post"]["subject"] == "《原神》长期项目启动·概念PV"
    assert len(post_full_info["post"]["post"]["images"]) == 1
    post_soup = BeautifulSoup(post_full_info["post"]["post"]["content"], features="html.parser")
    assert post_soup.find_all('p')


# noinspection PyShadowingNames
@pytest.mark.asyncio
@flaky(3, 1)
async def test_get_images_by_post_id(hyperion):
    post_images = await hyperion.get_images_by_post_id(2, 29023709)
    assert len(post_images) == 1
