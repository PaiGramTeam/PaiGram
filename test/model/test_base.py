import unittest
import json

from model.game.artifact import ArtifactInfo
from model.base import GameItem


class TestBase(unittest.TestCase):
    def test_game_item(self):
        test_dict = {"item_id": 0, "name": "攻击力", "type": "atk", "value": 2333}
        test_json = json.dumps(test_dict)
        test_game_item = GameItem(0, "攻击力", "atk", 2333)
        new_json = test_game_item.to_json()
        self.assertEqual(new_json, test_json)

    def test_artifact(self):
        test_dict = {"item_id": 0, "name": "测试花", "pos": "测试属性", "star": 2333,
                     "sub_item": [{"item_id": 0, "name": "攻击力", "type": "atk", "value": 2333}],
                     "main_item": {"item_id": 0, "name": "攻击力", "type": "atk", "value": 2333}, "level": 2333}
        test_json = json.dumps(test_dict)
        test_game_item = GameItem(0, "攻击力", "atk", 2333)
        test_artifact = ArtifactInfo(0, "测试花", 2333, test_game_item, "测试属性", 2333, [test_game_item])
        new_json = test_artifact.to_json()
        self.assertEqual(test_json, new_json)


if __name__ == '__main__':
    unittest.main()
