import unittest
from unittest import IsolatedAsyncioTestCase

from modules.apihelper.artifact import ArtifactOcrRate


class TestArtifact(IsolatedAsyncioTestCase):
    def setUp(self):
        self.artifact_rate = ArtifactOcrRate()

    async def test_get_artifact_attr(self):
        await self.artifact_rate.get_artifact_attr(b"")

    async def test_rate_artifact(self):
        artifact_attr = {
            'name': '翠绿的猎人之冠', 'pos': '理之冠', 'star': 5, 'level': 20,
            'main_item': {'type': 'cr', 'name': '暴击率', 'value': '31.1%'},
            'sub_item': [{'type': 'hp', 'name': '生命值', 'value': '9.3%'},
                         {'type': 'df', 'name': '防御力', 'value': '46'},
                         {'type': 'atk', 'name': '攻击力', 'value': '49'},
                         {'type': 'cd', 'name': '暴击伤害', 'value': '10.9%'}]}
        await self.artifact_rate.rate_artifact(artifact_attr)

    async def asyncTearDown(self) -> None:
        await self.artifact_rate.close()


if __name__ == "__main__":
    unittest.main()
