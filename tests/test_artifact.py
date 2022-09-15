import logging

import aiofiles
import pytest
import pytest_asyncio
from flaky import flaky

from modules.apihelper.artifact import ArtifactOcrRate

LOGGER = logging.getLogger(__name__)


@pytest_asyncio.fixture
async def artifact_rate():
    _artifact_rate = ArtifactOcrRate()
    yield _artifact_rate
    await _artifact_rate.close()


# noinspection PyShadowingNames
@pytest.mark.asyncio
class TestArtifactOcrRate:

    @staticmethod
    @flaky(3, 1)
    async def test_rate_artifact(artifact_rate):
        artifact_attr = {
            'name': '翠绿的猎人之冠', 'pos': '理之冠', 'star': 5, 'level': 20,
            'main_item': {'type': 'cr', 'name': '暴击率', 'value': '31.1%'},
            'sub_item': [{'type': 'hp', 'name': '生命值', 'value': '9.3%'},
                         {'type': 'df', 'name': '防御力', 'value': '46'},
                         {'type': 'atk', 'name': '攻击力', 'value': '49'},
                         {'type': 'cd', 'name': '暴击伤害', 'value': '10.9%'}]}
        assert await artifact_rate.rate_artifact(artifact_attr)

    @staticmethod
    @flaky(3, 1)
    async def test_ocr_artifact(artifact_rate):
        async with aiofiles.open("tests/data/test_artifact.jpg", mode="rb") as f:
            photo = await f.read()
        data = await artifact_rate.get_artifact_attr(photo)
        LOGGER.info(data.text)
        assert data.status_code == 200
