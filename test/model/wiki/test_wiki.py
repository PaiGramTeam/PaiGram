import unittest
from unittest import IsolatedAsyncioTestCase

from models.wiki.character import Character
from models.wiki.weapon import Weapon


class TestWeapon(IsolatedAsyncioTestCase):
    async def test_get_by_id(self):
        weapon = await Weapon.get_by_id('11417')
        self.assertEqual(weapon.name, '原木刀')
        self.assertEqual(weapon.rarity, 4)
        self.assertEqual(weapon.attack, 43.73)
        self.assertEqual(weapon.attribute.type.value, '攻击力')
        self.assertEqual(weapon.affix.name, '森林的瑞佑')

    async def test_get_by_name(self):
        weapon = await Weapon.get_by_name('风鹰剑')
        self.assertEqual(weapon.id, 11501)
        self.assertEqual(weapon.rarity, 5)
        self.assertEqual(weapon.attack, 47.54)
        self.assertEqual(weapon.attribute.type.value, '物理伤害加成')
        self.assertEqual(weapon.affix.name, '西风之鹰的抗争')
        self.assertTrue('听凭风引，便是正义与自由之风' in weapon.story)


class TestCharacter(IsolatedAsyncioTestCase):
    async def test_get_by_id(self):
        character = await Character.get_by_id('ayaka_002')
        self.assertEqual(character.name, '神里绫华')
        self.assertEqual(character.title, '白鹭霜华')
        self.assertEqual(character.occupation, '社奉行')
        self.assertEqual(character.association.value, '稻妻')
        self.assertEqual(character.cn_cv, '小N')

    async def test_get_by_name(self):
        character = await Character.get_by_name('神里绫华')
        self.assertEqual(character.id, 'ayaka_002')
        self.assertEqual(character.title, '白鹭霜华')
        self.assertEqual(character.occupation, '社奉行')
        self.assertEqual(character.association.value, '稻妻')
        self.assertEqual(character.cn_cv, '小N')

    async def test_get_full(self):
        async for character in Character.full_data_generator():
            print(character)


if __name__ == "__main__":
    unittest.main()
