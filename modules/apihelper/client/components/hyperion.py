import asyncio
import os
import re
from typing import List

from ..base.hyperionrequest import HyperionRequest
from ...models.genshin.hyperion import PostInfo, ArtworkImage
from ...typedefs import JSON_DATA

__all__ = ("Hyperion",)


class Hyperion:
    """米忽悠bbs相关API请求

    该名称来源于米忽悠的安卓BBS包名结尾，考虑到大部分重要的功能确实是在移动端实现了
    """

    POST_FULL_URL = "https://bbs-api.miyoushe.com/post/wapi/getPostFull"
    POST_FULL_IN_COLLECTION_URL = "https://bbs-api.miyoushe.com/post/wapi/getPostFullInCollection"
    GET_NEW_LIST_URL = "https://bbs-api.miyoushe.com/post/wapi/getNewsList"
    GET_OFFICIAL_RECOMMENDED_POSTS_URL = "https://bbs-api.miyoushe.com/post/wapi/getOfficialRecommendedPosts"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.72 Safari/537.36"
    )

    def __init__(self, *args, **kwargs):
        self.client = HyperionRequest(headers=self.get_headers(), *args, **kwargs)

    @staticmethod
    def extract_post_id(text: str) -> int:
        """
        :param text:
            # https://bbs.mihoyo.com/ys/article/8808224
            # https://m.bbs.mihoyo.com/ys/article/8808224
            # https://www.miyoushe.com/ys/article/32497914
            # https://m.miyoushe.com/ys/#/article/32497914
        :return: post_id
        """
        rgx = re.compile(r"(?:bbs|www\.)?(?:miyoushe|mihoyo)\.com/[^.]+/article/(?P<article_id>\d+)")
        matches = rgx.search(text)
        if matches is None:
            return -1
        entries = matches.groupdict()
        if entries is None:
            return -1
        try:
            art_id = int(entries.get("article_id"))
        except (IndexError, ValueError, TypeError):
            return -1
        return art_id

    def get_headers(self, referer: str = "https://www.miyoushe.com/ys/"):
        return {"User-Agent": self.USER_AGENT, "Referer": referer}

    @staticmethod
    def get_list_url_params(forum_id: int, is_good: bool = False, is_hot: bool = False, page_size: int = 20) -> dict:
        return {
            "forum_id": forum_id,
            "gids": 2,
            "is_good": is_good,
            "is_hot": is_hot,
            "page_size": page_size,
            "sort_type": 1,
        }

    @staticmethod
    def get_images_params(
        resize: int = 600, quality: int = 80, auto_orient: int = 0, interlace: int = 1, images_format: str = "jpg"
    ):
        """
        image/resize,s_600/quality,q_80/auto-orient,0/interlace,1/format,jpg
        :param resize: 图片大小
        :param quality: 图片质量
        :param auto_orient: 自适应
        :param interlace: 未知
        :param images_format: 图片格式
        :return:
        """
        params = (
            f"image/resize,s_{resize}/quality,q_{quality}/auto-orient,"
            f"{auto_orient}/interlace,{interlace}/format,{images_format}"
        )
        return {"x-oss-process": params}

    async def get_official_recommended_posts(self, gids: int) -> JSON_DATA:
        params = {"gids": gids}
        response = await self.client.get(url=self.GET_OFFICIAL_RECOMMENDED_POSTS_URL, params=params)
        return response

    async def get_post_full_in_collection(self, collection_id: int, gids: int = 2, order_type=1) -> JSON_DATA:
        params = {"collection_id": collection_id, "gids": gids, "order_type": order_type}
        response = await self.client.get(url=self.POST_FULL_IN_COLLECTION_URL, params=params)
        return response

    async def get_post_info(self, gids: int, post_id: int, read: int = 1) -> PostInfo:
        params = {"gids": gids, "post_id": post_id, "read": read}
        response = await self.client.get(self.POST_FULL_URL, params=params)
        return PostInfo.paste_data(response)

    async def get_images_by_post_id(self, gids: int, post_id: int) -> List[ArtworkImage]:
        post_info = await self.get_post_info(gids, post_id)
        art_list = []
        task_list = [
            self.download_image(post_info.post_id, post_info.image_urls[page], page)
            for page in range(len(post_info.image_urls))
        ]
        result_lists = await asyncio.gather(*task_list)
        for result_list in result_lists:
            for result in result_list:
                if isinstance(result, ArtworkImage):
                    art_list.append(result)

        def take_page(elem: ArtworkImage):
            return elem.page

        art_list.sort(key=take_page)
        return art_list

    async def download_image(self, art_id: int, url: str, page: int = 0) -> List[ArtworkImage]:
        filename = os.path.basename(url)
        _, file_extension = os.path.splitext(filename)
        is_image = bool(file_extension in ".jpg" or file_extension in ".png")
        response = await self.client.get(
            url, params=self.get_images_params(resize=2000) if is_image else None, de_json=False
        )
        return ArtworkImage.gen(
            art_id=art_id, page=page, file_name=filename, file_extension=url.split(".")[-1], data=response.content
        )

    async def get_new_list(self, gids: int, type_id: int, page_size: int = 20):
        """
        ?gids=2&page_size=20&type=3
        :return:
        """
        params = {"gids": gids, "page_size": page_size, "type": type_id}
        response = await self.client.get(url=self.GET_NEW_LIST_URL, params=params)
        return response

    async def close(self):
        await self.client.shutdown()
