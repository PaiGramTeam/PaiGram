import pytest
import pytest_asyncio
from flaky import flaky

from modules.apihelper.hyperion import Hyperion


@pytest_asyncio.fixture
async def hyperion():
    _hyperion = Hyperion()
    yield _hyperion
    await _hyperion.close()


# noinspection PyShadowingNames
@pytest.mark.asyncio
@flaky(3, 1)
async def test_post(hyperion):
    post_id = 29023709
    post_full_info = await hyperion.get_post_full_info(2, post_id)
    post_images = await hyperion.get_images_by_post_id(2, post_id)
    assert post_full_info
    assert len(post_images) == 1
