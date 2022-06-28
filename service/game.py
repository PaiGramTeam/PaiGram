from model.apihelper.hyperion import Hyperion
from service.cache import RedisCache
from service.repository import AsyncRepository


class GetGameInfo:
    def __init__(self, repository: AsyncRepository, cache: RedisCache):
        self.repository = repository
        self.cache = cache
        self.hyperion = Hyperion()

    async def get_characters_cultivation_atlas(self, character_name: str) -> str:
        qname = f"game:info:characters_cultivation_atlas:{character_name}"
        url_info = await self.cache.get_str_list(qname)
        if len(url_info) >= 1:
            url = url_info[-1]
            if url != "":
                return url_info[-1]

        async def get_post_id(collection_id: int) -> int:
            post_full_in_collection = await self.hyperion.get_post_full_in_collection(collection_id)
            if post_full_in_collection.error:
                await self.cache.set_str_list(qname, [""], 3600)
                return -1
            _post_id: int = -1
            for post_data in post_full_in_collection.data["posts"]:
                topics = post_data["topics"]
                for topic in topics:
                    if character_name == topic["name"]:
                        _post_id = int(post_data["post"]["post_id"])
                        break
                if _post_id != -1:
                    break
            return _post_id

        post_id = await get_post_id(839176)
        if post_id == -1:
            post_id = await get_post_id(839179)
            if post_id == -1:
                post_id = await get_post_id(839181)
        if post_id == -1:
            await self.cache.set_str_list(qname, [""], 3600)
            return ""
        artwork_info = await self.hyperion.get_artwork_info(2, post_id)
        await self.cache.set_str_list(qname, artwork_info.results.image_url_list, 3600)
        return artwork_info.results.image_url_list[0]
