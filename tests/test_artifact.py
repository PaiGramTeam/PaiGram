import asyncio

import pytest

from modules.apihelper.artifact import ArtifactOcrRate


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def artifact_rate():
    artifact_rate = ArtifactOcrRate()
    yield artifact_rate
    event_loop.run_until_complete(artifact_rate.close())


@pytest.mark.asyncio
async def test_rate_artifact(artifact_rate):
    artifact_attr = {
        'name': '翠绿的猎人之冠', 'pos': '理之冠', 'star': 5, 'level': 20,
        'main_item': {'type': 'cr', 'name': '暴击率', 'value': '31.1%'},
        'sub_item': [{'type': 'hp', 'name': '生命值', 'value': '9.3%'},
                     {'type': 'df', 'name': '防御力', 'value': '46'},
                     {'type': 'atk', 'name': '攻击力', 'value': '49'},
                     {'type': 'cd', 'name': '暴击伤害', 'value': '10.9%'}]}
    assert await artifact_rate.rate_artifact(artifact_attr)
