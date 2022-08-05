from typing import List, Optional

from model.apihelper.hyperion import Hyperion
from .cache import GameStrategyCache


class GameStrategyService:

    def __init__(self, cache: GameStrategyCache, collections: Optional[List[int]] = None):
        self._cache = cache
        self._hyperion = Hyperion()
        if collections is None:
            self._collections = [839176, 839179, 839181]
        else:
            self._collections = collections

    async def _get_strategy_from_hyperion(self, collection_id: int, character_name: str) -> int:
        post_id: int = -1
        post_full_in_collection = await self._hyperion.get_post_full_in_collection(collection_id)
        if post_full_in_collection.error:
            return post_id
        for post_data in post_full_in_collection.data["posts"]:
            topics = post_data["topics"]
            for topic in topics:
                if character_name == topic["name"]:
                    post_id = int(post_data["post"]["post_id"])
                    break
            if post_id != -1:
                break
        return post_id

    async def get_strategy(self, character_name: str) -> str:
        cache = await self._cache.get_url_list(character_name)
        if len(cache) >= 1:
            return cache[-1]

        for collection_id in self._collections:
            post_id = await self._get_strategy_from_hyperion(collection_id, character_name)
            if post_id != -1:
                break
        else:
            return ""

        artwork_info = await self._hyperion.get_artwork_info(2, post_id)
        await self._cache.set_url_list(character_name, artwork_info.results.image_url_list)
        return artwork_info.results.image_url_list[0]
