from typing import List, Optional

from modules.apihelper.hyperion import Hyperion
from .cache import GameCache


class GameStrategyService:
    def __init__(self, cache: GameCache, collections: Optional[List[int]] = None):
        self._cache = cache
        self._hyperion = Hyperion()
        if collections is None:
            self._collections = [839176, 839179, 839181, 1180811]
        else:
            self._collections = collections
        self._special_posts = {"达达利亚": "21272578"}

    async def _get_strategy_from_hyperion(self, collection_id: int, character_name: str) -> int:
        if character_name in self._special_posts:
            return self._special_posts[character_name]
        post_id: int = -1
        post_full_in_collection = await self._hyperion.get_post_full_in_collection(collection_id)
        for post_data in post_full_in_collection["posts"]:
            title = post_data["post"]["subject"]
            topics = post_data["topics"]
            for topic in topics:
                if character_name == topic["name"]:
                    post_id = int(post_data["post"]["post_id"])
                    break
            if post_id == -1 and title and character_name in title:
                post_id = int(post_data["post"]["post_id"])
            if post_id != -1:
                break
        return post_id

    async def get_strategy(self, character_name: str) -> str:
        cache = await self._cache.get_url_list(character_name)
        if len(cache) >= 1:
            return cache[0]

        for collection_id in self._collections:
            post_id = await self._get_strategy_from_hyperion(collection_id, character_name)
            if post_id != -1:
                break
        else:
            return ""

        artwork_info = await self._hyperion.get_post_info(2, post_id)
        await self._cache.set_url_list(character_name, artwork_info.image_urls)
        return artwork_info.image_urls[0]


class GameMaterialService:
    def __init__(self, cache: GameCache, collections: Optional[List[int]] = None):
        self._cache = cache
        self._hyperion = Hyperion()
        self._collections = [428421, 1164644] if collections is None else collections
        self._special = ["雷电将军", "珊瑚宫心海", "菲谢尔", "托马", "八重神子", "九条裟罗", "辛焱", "神里绫华"]

    async def _get_material_from_hyperion(self, collection_id: int, character_name: str) -> int:
        post_id: int = -1
        post_full_in_collection = await self._hyperion.get_post_full_in_collection(collection_id)
        for post_data in post_full_in_collection["posts"]:
            topics = post_data["topics"]
            for topic in topics:
                if character_name == topic["name"]:
                    post_id = int(post_data["post"]["post_id"])
                    break
            if post_id != -1:
                break
            subject = post_data["post"]["subject"]
            if character_name in subject:
                post_id = int(post_data["post"]["post_id"])
            if post_id != -1:
                break
        return post_id

    async def get_material(self, character_name: str) -> str:
        cache = await self._cache.get_url_list(character_name)
        if len(cache) >= 1:
            image_url_list = cache
        else:
            for collection_id in self._collections:
                post_id = await self._get_material_from_hyperion(collection_id, character_name)
                if post_id != -1:
                    break
            else:
                return ""

            artwork_info = await self._hyperion.get_post_info(2, post_id)
            image_url_list = artwork_info.image_urls
            await self._cache.set_url_list(character_name, image_url_list)
        if len(image_url_list) == 0:
            return ""
        elif len(image_url_list) == 1:
            return image_url_list[0]
        elif character_name in self._special:
            return image_url_list[2]
        else:
            return image_url_list[1]
