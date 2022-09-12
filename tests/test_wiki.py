from modules.wiki.character import Character
from modules.wiki.material import Material
from modules.wiki.weapon import Weapon


class TestWeapon:

    async def test_get_by_id(self):
        weapon = await Weapon.get_by_id('11417')
        assert weapon.name == '原木刀'
        assert weapon.rarity == 4
        assert weapon.attack == 43.73
        assert weapon.attribute.type.value == '元素充能效率'
        assert weapon.affix.name == '森林的瑞佑'

    async def test_get_by_name(self):
        weapon = await Weapon.get_by_name('风鹰剑')
        assert weapon.id == 11501
        assert weapon.rarity == 5
        assert weapon.attack == 47.54
        assert weapon.attribute.type.value == '物理伤害加成'
        assert weapon.affix.name == '西风之鹰的抗争'
        assert '听凭风引，便是正义与自由之风' in weapon.story

    async def test_get_full_gen(self):
        async for weapon in Weapon.full_data_generator():
            assert isinstance(weapon, Weapon)

    async def test_get_full(self):
        full_data = await Weapon.get_full_data()
        for weapon in full_data:
            assert isinstance(weapon, Weapon)

    async def test_name_list(self):
        from httpx import URL
        async for name in Weapon._name_list_generator(with_url=True):
            assert isinstance(name[0], str)
            assert isinstance(name[1], URL)


class TestCharacter:
    async def test_get_by_id(self):
        character = await Character.get_by_id('ayaka_002')
        assert character.name == '神里绫华'
        assert character.title == '白鹭霜华'
        assert character.occupation == '社奉行'
        assert character.association.value == '稻妻'
        assert character.cn_cv == '小N'

    async def test_get_by_name(self):
        character = await Character.get_by_name('神里绫华')
        assert character.name == '神里绫华'
        assert character.title == '白鹭霜华'
        assert character.occupation == '社奉行'
        assert character.association.value == '稻妻'
        assert character.cn_cv == '小N'

        main_character = await Character.get_by_name('荧')
        assert main_character.constellation == '旅人座'
        assert main_character.cn_cv == '宴宁&多多poi'

    async def test_get_full(self):
        async for character in Character.full_data_generator():
            assert isinstance(character, Character)


class TestMaterial:
    async def test_get_full_gen(self):
        async for material in Material.full_data_generator():
            assert isinstance(material, Material)

    async def test_get_full(self):
        material_list = await Material.get_full_data()
        for material in material_list:
            assert isinstance(material, Material)


class TestAll:
    async def test_all_get_full(self):
        import asyncio
        materials, weapons, characters = tuple(await asyncio.gather(
            Material.get_full_data(),
            Weapon.get_full_data(),
            Character.get_full_data(),
            return_exceptions=True
        ))
        assert len(materials) == 120
        assert len(weapons) == 151
        assert len(characters) == 58
