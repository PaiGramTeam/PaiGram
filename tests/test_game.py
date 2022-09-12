import pytest
import pytest_asyncio

from modules.apihelper.hyperion import Hyperion


@pytest_asyncio.fixture
async def hyperion():
    _hyperion = Hyperion()
    yield _hyperion
    await _hyperion.close()


# noinspection PyShadowingNames
@pytest.mark.asyncio
async def test_get_strategy(hyperion):
    test_collection_id_list = [839176, 839179, 839181]
    test_result = ["温迪", "胡桃", "雷电将军"]

    async def get_post_id(_collection_id: int, character_name: str) -> str:
        post_full_in_collection = await hyperion.get_post_full_in_collection(_collection_id)
        if post_full_in_collection.error:
            raise RuntimeError(f"获取收藏信息错误，错误信息为：{post_full_in_collection.message}")
        for post_data in post_full_in_collection.data["posts"]:
            topics = post_data["topics"]
            for topic in topics:
                if character_name == topic["name"]:
                    return topic["name"]
        return ""

    for index, _ in enumerate(test_collection_id_list):
        second = test_result[index]
        first = await get_post_id(test_collection_id_list[index], second)
        assert first == second
