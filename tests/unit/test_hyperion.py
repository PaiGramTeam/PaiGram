import pytest
import pytest_asyncio
from flaky import flaky

from modules.apihelper.client.components.hyperion import Hyperion


@pytest_asyncio.fixture
async def hyperion():
    _hyperion = Hyperion()
    yield _hyperion
    await _hyperion.close()


# noinspection PyShadowingNames
@pytest.mark.asyncio
@flaky(3, 1)
async def test_get_strategy(hyperion):
    test_collection_id_list = [839176, 839179, 839181, 1180811]
    test_result = ["温迪", "胡桃", "雷电将军", "柯莱"]

    async def get_post_id(_collection_id: int, character_name: str) -> str:
        post_full_in_collection = await hyperion.get_post_full_in_collection(_collection_id)
        for post_data in post_full_in_collection["posts"]:
            topics = post_data["topics"]
            for topic in topics:
                if character_name == topic["name"]:
                    return topic["name"]
        return ""

    for index, _ in enumerate(test_collection_id_list):
        second = test_result[index]
        first = await get_post_id(test_collection_id_list[index], second)
        assert first == second
