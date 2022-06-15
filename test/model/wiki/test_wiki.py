import unittest
from unittest import IsolatedAsyncioTestCase

from model.wiki.characters import Characters
from model.wiki.weapons import Weapons

weapons = Weapons()


class TestWiki(IsolatedAsyncioTestCase):
    TEST_WEAPONS_URL = "https://genshin.honeyhunterworld.com/db/weapon/w_3405/?lang=CHS"
    TEST_CHARACTERS_URL = "https://genshin.honeyhunterworld.com/db/char/hutao/?lang=CHS"

    def setUp(self):
        self.weapons = Weapons()
        self.characters = Characters()

    async def test_get_weapon(self):
        weapon_info = await self.weapons.get_weapon_info(self.TEST_WEAPONS_URL)
        self.assertEqual(weapon_info["name"], "护摩之杖")
        self.assertEqual(weapon_info["description"], "在早已失落的古老祭仪中，使用的朱赤「柴火杖」。")
        self.assertEqual(weapon_info["atk"]["name"], "基础攻击力")
        self.assertEqual(weapon_info["atk"]["min"], 46)
        self.assertEqual(weapon_info["atk"]["max"], 608)
        self.assertEqual(weapon_info["secondary"]["name"], "暴击伤害")
        self.assertEqual(weapon_info["secondary"]["min"], 14.4)
        self.assertEqual(weapon_info["secondary"]["max"], 66.2)
        self.assertEqual(weapon_info["star"]["value"], 5)
        self.assertEqual(weapon_info["type"]["name"], "Polearm")
        self.assertEqual(weapon_info["passive_ability"]["name"], "无羁的朱赤之蝶")
        self.assertEqual(weapon_info["passive_ability"]["description"], "生命值提升20%。"
                                                                        "此外，基于装备该武器的角色生命值上限的0.8%，"
                                                                        "获得攻击力加成。当装备该武器的角色生命值低于50%时，"
                                                                        "进一步获得1%基于生命值上限的攻击力提升。")

    async def test_get_all_weapon_url(self):
        url_list = await self.weapons.get_all_weapon_url()
        self.assertEqual(True, len(url_list) >= 135)

    async def test_get_characters(self):
        characters_info = await self.characters.get_characters(self.TEST_CHARACTERS_URL)
        self.assertEqual(characters_info["name"], "胡桃")
        self.assertEqual(characters_info["title"], "雪霁梅香")
        self.assertEqual(characters_info["rarity"], 5)
        self.assertEqual(characters_info["description"], "「往生堂」七十七代堂主，年纪轻轻就已主掌璃月的葬仪事务。")
        self.assertEqual(characters_info["allegiance"], "往生堂")


if __name__ == "__main__":
    unittest.main()
