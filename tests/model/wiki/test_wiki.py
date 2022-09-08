import unittest
from unittest import IsolatedAsyncioTestCase

from modules.wiki.character import Character
from modules.wiki.material import Material
from modules.wiki.weapon import Weapon


class TestWeapon(IsolatedAsyncioTestCase):
    async def test_get_by_id(self):
        weapon = await Weapon.get_by_id('11417')
        self.assertEqual(weapon.name, '原木刀')
        self.assertEqual(weapon.rarity, 4)
        self.assertEqual(weapon.attack, 43.73)
        self.assertEqual(weapon.attribute.type.value, '元素充能效率')
        self.assertEqual(weapon.affix.name, '森林的瑞佑')

    async def test_get_by_name(self):
        weapon = await Weapon.get_by_name('风鹰剑')
        self.assertEqual(weapon.id, 11501)
        self.assertEqual(weapon.rarity, 5)
        self.assertEqual(weapon.attack, 47.54)
        self.assertEqual(weapon.attribute.type.value, '物理伤害加成')
        self.assertEqual(weapon.affix.name, '西风之鹰的抗争')
        self.assertTrue('听凭风引，便是正义与自由之风' in weapon.story)

    async def test_get_full_gen(self):
        async for weapon in Weapon.full_data_generator():
            self.assertIsInstance(weapon, Weapon)

    async def test_get_full(self):
        full_data = await Weapon.get_full_data()
        for weapon in full_data:
            self.assertIsInstance(weapon, Weapon)

    async def test_name_list(self):
        from httpx import URL
        async for name in Weapon._name_list_generator(with_url=True):
            self.assertIsInstance(name[0], str)
            self.assertIsInstance(name[1], URL)


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

        main_character = await Character.get_by_name('荧')
        self.assertEqual(main_character.constellation, '旅人座')
        self.assertEqual(main_character.cn_cv, '宴宁&多多poi')

    async def test_get_full(self):
        async for character in Character.full_data_generator():
            self.assertIsInstance(character, Character)


class TestMaterial(IsolatedAsyncioTestCase):
    async def test_get_full_gen(self):
        async for material in Material.full_data_generator():
            self.assertIsInstance(material, Material)

    async def test_get_full(self):
        material_list = await Material.get_full_data()
        for material in material_list:
            self.assertIsInstance(material, Material)


class TestAll(IsolatedAsyncioTestCase):
    async def test_all_get_full(self):
        import asyncio
        materials, weapons, characters = tuple(await asyncio.gather(
            Material.get_full_data(),
            Weapon.get_full_data(),
            Character.get_full_data(),
            return_exceptions=True
        ))
        self.assertEqual(len(materials), 120)
        self.assertEqual(len(weapons), 151)
        self.assertEqual(len(characters), 58)


if __name__ == "__main__":
    unittest.main()
