from typing import List, Optional

from core.base_service import BaseService
from core.services.game.cache import GameCacheForStrategy
from modules.apihelper.client.components.hyperion import Hyperion

__all__ = "GameStrategyService"


class GameStrategyService(BaseService):
    def __init__(self, cache: GameCacheForStrategy, collections: Optional[List[int]] = None):
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
