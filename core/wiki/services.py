import asyncio

import ujson

from logger import Log
from models.wiki.characters import Characters
from models.wiki.weapons import Weapons
from .cache import WikiCache


class WikiService:

    def __init__(self, cache: WikiCache):
        self._cache = cache
        """Redis 在这里的作用是作为持久化"""
        self.weapons = Weapons()
        self.characters = Characters()
        self._characters_list = []
        self._characters_name_list = []
        self._weapons_name_list = []
        self._weapons_list = []
        self.first_run = True

    async def refresh_weapon(self):
        weapon_url_list = await self.weapons.get_all_weapon_url()
        Log.info(f"一共找到 {len(weapon_url_list)} 把武器信息")
        weapons_list = []
        task_list = []
        for index, weapon_url in enumerate(weapon_url_list):
            task_list.append(self.weapons.get_weapon_info(weapon_url))
            # weapon_info = await self.weapons.get_weapon_info(weapon_url)
            if index % 5 == 0:
                result_list = await asyncio.gather(*task_list)
                weapons_list.extend(result for result in result_list if isinstance(result, dict))
                task_list.clear()
            if index % 10 == 0 and index != 0:
                Log.info(f"现在已经获取到 {index} 把武器信息")
        result_list = await asyncio.gather(*task_list)
        weapons_list.extend(result for result in result_list if isinstance(result, dict))

        Log.info("写入武器信息到Redis")
        self._weapons_list = weapons_list
        await self._cache.del_one("weapon")
        await self._cache.refresh_info_cache("weapon", weapons_list)

    async def refresh_characters(self):
        characters_url_list = await self.characters.get_all_characters_url()
        Log.info(f"一共找到 {len(characters_url_list)} 个角色信息")
        characters_list = []
        task_list = []
        for index, characters_url in enumerate(characters_url_list):
            task_list.append(self.characters.get_characters(characters_url))
            if index % 5 == 0:
                result_list = await asyncio.gather(*task_list)
                characters_list.extend(result for result in result_list if isinstance(result, dict))
                task_list.clear()
            if index % 10 == 0 and index != 0:
                Log.info(f"现在已经获取到 {index} 个角色信息")
        result_list = await asyncio.gather(*task_list)
        characters_list.extend(result for result in result_list if isinstance(result, dict))

        Log.info("写入角色信息到Redis")
        self._characters_list = characters_list
        await self._cache.del_one("characters")
        await self._cache.refresh_info_cache("characters", characters_list)

    async def refresh_wiki(self):
        """
        用于把Redis的缓存全部加载进Python
        :return:
        """
        Log.info("正在重新获取Wiki")
        Log.info("正在重新获取武器信息")
        await self.refresh_weapon()
        Log.info("正在重新获取角色信息")
        await self.refresh_characters()
        Log.info("刷新成功")

    async def init(self):
        """
        用于把Redis的缓存全部加载进Python
        :return:
        """
        if self.first_run:
            weapon_dict = await self._cache.get_one("weapon")
            self._weapons_list = ujson.loads(weapon_dict)
            for weapon in self._weapons_list:
                self._weapons_name_list.append(weapon["name"])
            characters_dict = await self._cache.get_one("characters")
            self._characters_list = ujson.loads(characters_dict)
            for characters in self._characters_list:
                self._characters_name_list.append(characters["name"])
            self.first_run = False

    async def get_weapons(self, name: str):
        await self.init()
        if len(self._weapons_list) == 0:
            return {}
        return next((weapon for weapon in self._weapons_list if weapon["name"] == name), {})

    async def get_weapons_name_list(self) -> list:
        await self.init()
        return self._weapons_name_list

    async def get_weapons_list(self) -> list:
        await self.init()
        return self._weapons_list

    async def get_characters_list(self) -> list:
        await self.init()
        return self._characters_list

    async def get_characters_name_list(self) -> list:
        await self.init()
        return self._characters_name_list
