import asyncio
import logging
from random import sample, randint
from typing import Type

import pytest
from flaky import flaky

from modules.wiki.base import WikiModel
from modules.wiki.character import Character
from modules.wiki.material import Material
from modules.wiki.weapon import Weapon

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.mark.asyncio
class TestWeapon:

    @staticmethod
    @flaky(3, 1)
    async def test_get_by_id():
        weapon = await Weapon.get_by_id('i_n11417')
        assert weapon.name == '原木刀'
        assert weapon.rarity == 4
        assert weapon.attack == 43.73
        assert weapon.attribute.type.value == '元素充能效率'
        assert weapon.affix.name == '森林的瑞佑'

    @staticmethod
    @flaky(3, 1)
    async def test_get_by_name():
        weapon = await Weapon.get_by_name('风鹰剑')
        assert weapon.id == 'i_n11501'
        assert weapon.rarity == 5
        assert weapon.attack == 47.54
        assert weapon.attribute.type.value == '物理伤害加成'
        assert weapon.affix.name == '西风之鹰的抗争'
        assert '听凭风引，便是正义与自由之风' in weapon.story

    @staticmethod
    @flaky(3, 1)
    async def test_name_list():
        from httpx import URL
        async for name in Weapon._name_list_generator(with_url=True):
            assert isinstance(name[0], str)
            assert isinstance(name[1], URL)


@pytest.mark.asyncio
class TestCharacter:

    @staticmethod
    @flaky(3, 1)
    async def test_get_by_id():
        character = await Character.get_by_id('ayaka_002')
        assert character.name == '神里绫华'
        assert character.title == '白鹭霜华'
        assert character.occupation == '社奉行'
        assert character.association.value == '稻妻'
        assert character.cn_cv == '小N'

    @staticmethod
    @flaky(3, 1)
    async def test_get_by_name():
        character = await Character.get_by_name('神里绫华')
        assert character.name == '神里绫华'
        assert character.title == '白鹭霜华'
        assert character.occupation == '社奉行'
        assert character.association.value == '稻妻'
        assert character.cn_cv == '小N'
        main_character = await Character.get_by_name('荧')
        assert main_character.constellation == '旅人座'
        assert main_character.cn_cv == '宴宁&多多poi'

    @staticmethod
    @flaky(3, 1)
    async def test_name_list():
        from httpx import URL
        async for name in Character._name_list_generator(with_url=True):
            assert isinstance(name[0], str)
            assert isinstance(name[1], URL)


@pytest.mark.asyncio
class TestMaterial:

    @staticmethod
    @flaky(3, 1)
    async def test_get_by_id():
        material = await Material.get_by_id('i_504')
        assert material.name == '高塔孤王的碎梦'
        assert material.type == '武器突破素材'
        assert '合成获得' in material.source
        assert '巴巴托斯' in material.description

        material = await Material.get_by_id('i_483')
        assert material.name == '凶将之手眼'
        assert material.type == '角色培养素材'
        assert '70级以上永恒的守护者挑战奖励' in material.source
        assert '所见即所为' in material.description

    @staticmethod
    @flaky(3, 1)
    async def test_get_by_name():
        material = await Material.get_by_name('地脉的新芽')
        assert material.id == 'i_73'
        assert material.type == '角色培养素材'
        assert '60级以上深渊法师掉落' in material.source
        assert '勃发' in material.description

        material = await Material.get_by_name('「黄金」的教导')
        assert material.id == 'i_431'
        assert material.type == '天赋培养素材'
        assert 2 in material.weekdays
        assert '土的象' in material.description

    @staticmethod
    @flaky(3, 1)
    async def test_name_list():
        from httpx import URL
        async for name in Material._name_list_generator(with_url=True):
            assert isinstance(name[0], str)
            assert isinstance(name[1], URL)


@pytest.mark.asyncio
class TestAll:

    @staticmethod
    @flaky(3, 1)
    async def make_test(target: Type[WikiModel]):
        from httpx import URL
        name_list = await target.get_name_list(with_url=True)
        name_len = len(name_list)
        assert name_len != 0
        test_len = randint(1, max(2, int(len(name_list) * 0.3)))  # nosec
        LOGGER.info("得到了 %d 条 %s 的数据, 将会测试其中的 %s 条数据", name_len, target.__name__, test_len)
        for name, url in sample(name_list, test_len):
            assert isinstance(name, str)
            assert isinstance(url, URL)
            instance = await target._scrape(url)
            assert isinstance(instance, target)
            LOGGER.info("%s is ok.", instance.name)

    @flaky(3, 1)
    async def test_random_material(self):
        await self.make_test(Material)

    @flaky(3, 1)
    async def test_random_weapon(self):
        await self.make_test(Weapon)

    @flaky(3, 1)
    async def test_random_character(self):
        await self.make_test(Character)
