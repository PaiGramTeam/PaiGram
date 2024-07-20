import asyncio
import os
import re
from abc import abstractmethod
from time import time
from typing import List, Tuple, Dict

from ..base.hyperionrequest import HyperionRequest
from ...models.genshin.hyperion import (
    PostInfo,
    ArtworkImage,
    LiveInfo,
    LiveCode,
    LiveCodeHoYo,
    PostRecommend,
    PostTypeEnum,
)
from ...typedefs import JSON_DATA

__all__ = (
    "HyperionBase",
    "Hyperion",
)


class HyperionBase:
    @staticmethod
    def extract_post_id(text: str) -> Tuple[int, PostTypeEnum]:
        """
        :param text:
            # https://bbs.mihoyo.com/ys/article/8808224
            # https://m.bbs.mihoyo.com/ys/article/8808224
            # https://www.miyoushe.com/ys/article/32497914
            # https://m.miyoushe.com/ys/#/article/32497914
        :return: post_id
        """
        rgx = re.compile(r"(?:bbs|www\.)?(?:miyoushe|mihoyo)\.(.*)/[^.]+/article/(?P<article_id>\d+)")
        rgx2 = re.compile(r"(?:bbs|www\.)?(?:hoyolab|hoyoverse)\.(.*)/article/(?P<article_id>\d+)")
        matches = rgx.search(text) or rgx2.search(text)
        if matches is None:
            return -1, PostTypeEnum.NULL
        entries = matches.groupdict()
        if entries is None:
            return -1, PostTypeEnum.NULL
        try:
            art_id = int(entries.get("article_id"))
            post_type = PostTypeEnum.CN if "miyoushe" in text or "mihoyo" in text else PostTypeEnum.OS
        except (IndexError, ValueError, TypeError):
            return -1, PostTypeEnum.NULL
        return art_id, post_type

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
        :param interlace: 图片渐进显示
        :param images_format: 图片格式
        :return:
        """
        params = (
            f"image/resize,s_{resize}/quality,q_{quality}/auto-orient,"
            f"{auto_orient}/interlace,{interlace}/format,{images_format}"
        )
        return {"x-oss-process": params}

    @staticmethod
    async def get_images_by_post_id_tasks(task_list: List) -> List[ArtworkImage]:
        art_list = []
        result_lists = await asyncio.gather(*task_list)
        for result_list in result_lists:
            for result in result_list:
                if isinstance(result, ArtworkImage):
                    art_list.append(result)

        def take_page(elem: ArtworkImage):
            return elem.page

        art_list.sort(key=take_page)
        return art_list

    @staticmethod
    async def download_image(client: "HyperionRequest", art_id: int, url: str, page: int = 0) -> List[ArtworkImage]:
        filename = os.path.basename(url)
        _, _file_extension = os.path.splitext(filename)
        file_extension = _file_extension.lower()
        is_image = file_extension in ".jpg" or file_extension in ".jpeg" or file_extension in ".png"
        response = await client.get(
            url, params=Hyperion.get_images_params(resize=2000) if is_image else None, de_json=False
        )
        return ArtworkImage.gen(
            art_id=art_id, page=page, file_name=filename, file_extension=url.split(".")[-1], data=response.content
        )

    @abstractmethod
    async def get_new_list(self, gids: int, type_id: int, page_size: int = 20) -> Dict:
        """获取最新帖子"""

    @abstractmethod
    async def get_new_list_recommended_posts(self, gids: int, type_id: int, page_size: int = 20) -> List[PostRecommend]:
        """获取最新帖子"""

    @abstractmethod
    async def get_official_recommended_posts(self, gids: int) -> List[PostRecommend]:
        """获取官方推荐帖子"""

    @abstractmethod
    async def get_post_info(self, gids: int, post_id: int, read: int = 1) -> PostInfo:
        """获取帖子信息"""

    @abstractmethod
    async def get_images_by_post_id(self, gids: int, post_id: int) -> List[ArtworkImage]:
        """获取帖子图片"""

    @abstractmethod
    async def close(self):
        """关闭请求会话"""


class Hyperion(HyperionBase):
    """米忽悠bbs相关API请求

    该名称来源于米忽悠的安卓BBS包名结尾，考虑到大部分重要的功能确实是在移动端实现了
    """

    POST_FULL_URL = "https://bbs-api.miyoushe.com/post/wapi/getPostFull"
    POST_FULL_IN_COLLECTION_URL = "https://bbs-api.miyoushe.com/post/wapi/getPostFullInCollection"
    GET_NEW_LIST_URL = "https://bbs-api.miyoushe.com/post/wapi/getNewsList"
    GET_OFFICIAL_RECOMMENDED_POSTS_URL = "https://bbs-api.miyoushe.com/post/wapi/getOfficialRecommendedPosts"
    LIVE_INFO_URL = "https://api-takumi.mihoyo.com/event/miyolive/index"
    LIVE_CODE_URL = "https://api-takumi-static.mihoyo.com/event/miyolive/refreshCode"
    LIVE_CODE_HOYO_URL = "https://bbs-api-os.hoyolab.com/community/painter/wapi/circle/channel/guide/material"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.72 Safari/537.36"
    )

    def __init__(self, *args, **kwargs):
        self.client = HyperionRequest(headers=self.get_headers(), *args, **kwargs)

    def get_headers(self, referer: str = "https://www.miyoushe.com/ys/"):
        return {"User-Agent": self.USER_AGENT, "Referer": referer}

    async def get_official_recommended_posts(self, gids: int) -> List[PostRecommend]:
        results = []
        tasks = [self.get_new_list_recommended_posts(gids, i, 5) for i in range(1, 4)]
        asyncio_results = await asyncio.gather(*tasks)
        for result in asyncio_results:
            results.extend(result)
        return results

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
        task_list = [
            self._download_image(post_info.post_id, post_info.image_urls[page], page)
            for page in range(len(post_info.image_urls))
        ]
        return await self.get_images_by_post_id_tasks(task_list)

    async def _download_image(self, art_id: int, url: str, page: int = 0) -> List[ArtworkImage]:
        return await self.download_image(self.client, art_id, url, page)

    async def get_new_list(self, gids: int, type_id: int, page_size: int = 20) -> Dict:
        params = {"gids": gids, "page_size": page_size, "type": type_id}
        return await self.client.get(url=self.GET_NEW_LIST_URL, params=params)

    async def get_new_list_recommended_posts(self, gids: int, type_id: int, page_size: int = 20) -> List[PostRecommend]:
        resp = await self.get_new_list(gids, type_id, page_size)
        data = resp["list"]
        return [PostRecommend.parse(i) for i in data]

    async def get_live_info(self, act_id: str) -> LiveInfo:
        headers = {"x-rpc-act_id": act_id}
        response = await self.client.get(url=self.LIVE_INFO_URL, headers=headers)
        return LiveInfo(**response["live"])

    async def get_live_code(self, act_id: str, ver_code: str) -> List[LiveCode]:
        headers = {"x-rpc-act_id": act_id}
        params = {
            "version": ver_code,
            "time": str(int(time())),
        }
        response = await self.client.get(url=self.LIVE_CODE_URL, headers=headers, params=params)
        codes = []
        for code_data in response.get("code_list", []):
            codes.append(LiveCode(**code_data))
        return codes

    async def get_live_code_hoyo(self, gid: int) -> List[LiveCodeHoYo]:
        headers = self.get_headers("https://www.hoyolab.com/")
        headers.update(
            {
                "x-rpc-app_version": "2.50.0",
                "x-rpc-client_type": "4",
                "x-rpc-language": "zh-cn",
            }
        )
        params = {
            "game_id": str(gid),
        }
        codes = []
        response = await self.client.get(url=self.LIVE_CODE_HOYO_URL, headers=headers, params=params)
        guess_offline_at = LiveCodeHoYo.guess_offline_at()
        for module in response.get("modules", []):
            if exchange_group := module.get("exchange_group"):
                for code_data in exchange_group.get("bonuses", []):
                    codes.append(LiveCodeHoYo(**code_data))
                break
        for _ in range(len(codes), 3):
            codes.append(LiveCodeHoYo(exchange_code="", offline_at=guess_offline_at))
        return codes

    async def close(self):
        await self.client.shutdown()
