from typing import List, NoReturn, Optional

from core.base_service import BaseService
from core.services.wiki.cache import WikiCache
from modules.wiki.character import Character
from modules.wiki.weapon import Weapon
from utils.log import logger

__all__ = ["WikiService"]


class WikiService(BaseService):
    def __init__(self, cache: WikiCache):
        self._cache = cache
        """Redis 在这里的作用是作为持久化"""
        self._character_list = []
        self._character_name_list = []
        self._weapon_name_list = []
        self._weapon_list = []
        self.first_run = True

    async def refresh_weapon(self) -> NoReturn:
        weapon_name_list = await Weapon.get_name_list()
        logger.info("一共找到 %s 把武器信息", len(weapon_name_list))

        weapon_list = []
        num = 0
        async for weapon in Weapon.full_data_generator():
            weapon_list.append(weapon)
            num += 1
            if num % 10 == 0:
                logger.info("现在已经获取到 %s 把武器信息", num)

        logger.info("写入武器信息到Redis")
        self._weapon_list = weapon_list
        await self._cache.delete("weapon")
        await self._cache.set("weapon", [i.json() for i in weapon_list])

    async def refresh_characters(self) -> NoReturn:
        character_name_list = await Character.get_name_list()
        logger.info("一共找到 %s 个角色信息", len(character_name_list))

        character_list = []
        num = 0
        async for character in Character.full_data_generator():
            character_list.append(character)
            num += 1
            if num % 10 == 0:
                logger.info("现在已经获取到 %s 个角色信息", num)

        logger.info("写入角色信息到Redis")
        self._character_list = character_list
        await self._cache.delete("characters")
        await self._cache.set("characters", [i.json() for i in character_list])

    async def refresh_wiki(self) -> NoReturn:
        """
        用于把Redis的缓存全部加载进Python
        :return:
        """

        await self.refresh_characters()

    async def init(self) -> NoReturn:
        """
        用于把Redis的缓存全部加载进Python
        :return:
        """
        if self.first_run:
            weapon_dict = await self._cache.get("weapon")
            self._weapon_list = [Weapon.parse_obj(obj) for obj in weapon_dict]
            self._weapon_name_list = [weapon.name for weapon in self._weapon_list]
            characters_dict = await self._cache.get("characters")
            self._character_list = [Character.parse_obj(obj) for obj in characters_dict]
            self._character_name_list = [character.name for character in self._character_list]

            self.first_run = False

    async def get_weapons(self, name: str) -> Optional[Weapon]:
        await self.init()
        if len(self._weapon_list) == 0:
            return None
        return next((weapon for weapon in self._weapon_list if weapon.name == name), None)

    async def get_weapons_name_list(self) -> List[str]:
        await self.init()
        return self._weapon_name_list

    async def get_weapons_list(self) -> List[Weapon]:
        await self.init()
        return self._weapon_list

    async def get_characters_list(self) -> List[Character]:
        await self.init()
        return self._character_list

    async def get_characters_name_list(self) -> List[str]:
        await self.init()
        return self._character_name_list
