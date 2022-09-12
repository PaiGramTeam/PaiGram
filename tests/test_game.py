import asyncio

import pytest

from modules.apihelper.hyperion import Hyperion


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def hyperion(event_loop):
    hyperion = Hyperion()
    yield hyperion
    event_loop.run_until_complete(hyperion.close())


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
