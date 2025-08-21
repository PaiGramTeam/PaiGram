import asyncio
from typing import List, Dict

from .hyperion import HyperionBase
from ..base.hyperionrequest import HyperionRequest
from ...models.genshin.hyperion import PostInfo, ArtworkImage, PostRecommend, HoYoPostMultiLang

__all__ = ("Hoyolab",)


class Hoyolab(HyperionBase):
    POST_FULL_URL = "https://bbs-api-os.hoyolab.com/community/post/wapi/getPostFull"
    GET_NEW_LIST_URL = "https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList"
    NEW_BG_URL = "https://bbs-api-os.hoyolab.com/community/painter/wapi/circle/info"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.72 Safari/537.36"
    )

    def __init__(self, *args, **kwargs):
        self.client = HyperionRequest(headers=self.get_headers(), *args, **kwargs)

    def get_headers(self, lang: str = ""):
        lang = lang or self.LANG
        return {
            "User-Agent": self.USER_AGENT,
            "Referer": "https://www.hoyolab.com/",
            "X-Rpc-Language": lang,
        }

    async def get_official_recommended_posts(self, gids: int) -> List[PostRecommend]:
        results = []
        tasks = [self.get_new_list_recommended_posts(gids, i, 5, self.LANG) for i in range(1, 4)]
        asyncio_results = await asyncio.gather(*tasks)
        for result in asyncio_results:
            results.extend(result)
        post_ids = [post.post_id for post in results]
        tasks = [self.get_new_list_recommended_posts(gids, i, 5, "en-us") for i in range(1, 4)]
        asyncio_results = await asyncio.gather(*tasks)
        for result in asyncio_results:
            for post in result:
                if post.post_id not in post_ids:
                    results.append(post)
        return results

    async def get_post_info(self, gids: int, post_id: int, read: int = 1, scene: int = 1, lang: str = "") -> PostInfo:
        params = {"post_id": post_id, "read": read, "scene": scene}
        response = await self.client.get(self.POST_FULL_URL, params=params, headers=self.get_headers(lang=lang))
        return PostInfo.paste_data(response, hoyolab=True)

    async def get_images_by_post_id(self, gids: int, post_id: int) -> List[ArtworkImage]:
        post_info = await self.get_post_info(gids, post_id)
        task_list = [
            self._download_image(post_info.post_id, post_info.image_urls[page], page)
            for page in range(len(post_info.image_urls))
        ]
        return await self.get_images_by_post_id_tasks(task_list)

    async def _download_image(self, art_id: int, url: str, page: int = 0) -> List[ArtworkImage]:
        return await self.download_image(self.client, art_id, url, page)

    async def get_new_list(self, gids: int, type_id: int, page_size: int = 20, lang: str = "") -> Dict:
        params = {"gids": gids, "page_size": page_size, "type": type_id}
        return await self.client.get(url=self.GET_NEW_LIST_URL, params=params, headers=self.get_headers(lang=lang))

    async def get_new_list_recommended_posts(
        self, gids: int, type_id: int, page_size: int = 20, lang: str = ""
    ) -> List[PostRecommend]:
        resp = await self.get_new_list(gids, type_id, page_size, lang)
        data = resp["list"]
        return [PostRecommend.parse(i) for i in data]

    async def close(self):
        await self.client.shutdown()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
