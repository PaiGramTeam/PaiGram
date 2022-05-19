import asyncio
import re
from typing import List
import httpx
from httpx import AsyncClient
from .base import MiHoYoBBSResponse, ArtworkImage, BaseResponseData
from .helpers import get_ds, get_device_id


class Mihoyo:
    POST_FULL_URL = "https://bbs-api.mihoyo.com/post/wapi/getPostFull"
    POST_FULL_IN_COLLECTION_URL = "https://bbs-api.mihoyo.com/post/wapi/getPostFullInCollection"
    GET_NEW_LIST_URL = "https://bbs-api.mihoyo.com/post/wapi/getNewsList"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                 "Chrome/90.0.4430.72 Safari/537.36"

    def __init__(self):
        self.client = httpx.AsyncClient(headers=self.get_headers())

    @staticmethod
    def extract_post_id(text: str) -> int:
        """
        :param text:
            # https://bbs.mihoyo.com/ys/article/8808224
            # https://m.bbs.mihoyo.com/ys/article/8808224
        :return: post_id
        """
        rgx = re.compile(r"(?:bbs\.)?mihoyo\.com/[^.]+/article/(\d+)")
        args = rgx.split(text)
        if args is None:
            return -1
        try:
            art_id = int(args[1])
        except (IndexError, ValueError):
            return -1
        return art_id

    def get_headers(self, referer: str = "https://bbs.mihoyo.com/"):
        return {
            "User-Agent": self.USER_AGENT,
            "Referer": referer
        }

    @staticmethod
    def get_list_url_params(forum_id: int, is_good: bool = False, is_hot: bool = False,
                            page_size: int = 20) -> dict:
        params = {
            "forum_id": forum_id,
            "gids": 2,
            "is_good": is_good,
            "is_hot": is_hot,
            "page_size": page_size,
            "sort_type": 1
        }

        return params

    @staticmethod
    def get_images_params(resize: int = 600, quality: int = 80, auto_orient: int = 0, interlace: int = 1,
                          images_format: str = "jpg"):
        """
        image/resize,s_600/quality,q_80/auto-orient,0/interlace,1/format,jpg
        :param resize: 图片大小
        :param quality: 图片质量
        :param auto_orient: 自适应
        :param interlace: 未知
        :param images_format: 图片格式
        :return:
        """
        params = f"image/resize,s_{resize}/quality,q_{quality}/auto-orient," \
                 f"{auto_orient}/interlace,{interlace}/format,{images_format}"
        return {"x-oss-process": params}

    async def get_post_full_in_collection(self, collection_id: int, gids: int = 2, order_type=1) -> BaseResponseData:
        params = {
            "collection_id": collection_id,
            "gids": gids,
            "order_type": order_type
        }
        response = await self.client.get(url=self.POST_FULL_IN_COLLECTION_URL, params=params)
        if response.is_error:
            return BaseResponseData(error_message="请求错误")
        return BaseResponseData(response.json())

    async def get_artwork_info(self, gids: int, post_id: int, read: int = 1) -> MiHoYoBBSResponse:
        params = {
            "gids": gids,
            "post_id": post_id,
            "read": read
        }
        response = await self.client.get(self.POST_FULL_URL, params=params)
        if response.is_error:
            return MiHoYoBBSResponse(error_message="请求错误")
        return MiHoYoBBSResponse(response.json())

    async def get_post_full_info(self, gids: int, post_id: int, read: int = 1) -> BaseResponseData:
        params = {
            "gids": gids,
            "post_id": post_id,
            "read": read
        }
        response = await self.client.get(self.POST_FULL_URL, params=params)
        if response.is_error:
            return BaseResponseData(error_message="请求错误")
        return BaseResponseData(response.json())


    async def get_images_by_post_id(self, gids: int, post_id: int) -> List[ArtworkImage]:
        artwork_info = await self.get_artwork_info(gids, post_id)
        if artwork_info.error:
            return []
        urls = artwork_info.results.image_url_list
        art_list = []
        task_list = [
            self.download_image(artwork_info.post_id, urls[page], page) for page in range(len(urls))
        ]
        result_list = await asyncio.gather(*task_list)
        for result in result_list:
            if isinstance(result, ArtworkImage):
                art_list.append(result)

        def take_page(elem: ArtworkImage):
            return elem.page

        art_list.sort(key=take_page)
        return art_list

    async def download_image(self, art_id: int, url: str, page: int = 0) -> ArtworkImage:
        response = await self.client.get(url, params=self.get_images_params(resize=2000), timeout=5)
        if response.is_error:
            return ArtworkImage(art_id, page, True)
        return ArtworkImage(art_id, page, data=response.content)

    async def get_new_list(self, gids: int, type_id: int, page_size: int = 20):
        """
        ?gids=2&page_size=20&type=3
        :return:
        """
        params = {
            "gids": gids,
            "page_size": page_size,
            "type": type_id
        }
        response = await self.client.get(url=self.GET_NEW_LIST_URL, params=params)
        if response.is_error:
            return BaseResponseData(error_message="请求错误")
        return BaseResponseData(response.json())

    async def close(self):
        await self.client.aclose()


class YuanShen:
    SIGN_INFO_URL = "https://api-takumi.mihoyo.com/event/bbs_sign_reward/info"
    SIGN_URL = "https://api-takumi.mihoyo.com/event/bbs_sign_reward/sign"
    SIGN_HOME_URL = "https://api-takumi.mihoyo.com/event/bbs_sign_reward/home"

    APP_VERSION = "2.3.0"
    USER_AGENT = "Mozilla/5.0 (Linux; Android 9; Unspecified Device) AppleWebKit/537.36 (KHTML, like Gecko) " \
                 "Version/4.0 Chrome/39.0.0.0 Mobile Safari/537.36 miHoYoBBS/2.3.0"
    REFERER = "https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html?" \
              "bbs_auth_required=true&act_id=e202009291139501&utm_source=bbs&utm_medium=mys&utm_campaign=icon"
    ORIGIN = "https://webstatic.mihoyo.com"

    ACT_ID = "e202009291139501"
    DS_SALT = "h8w582wxwgqvahcdkpvdhbh2w9casgfl"

    def __init__(self):
        self.headers = {
            "Origin": self.ORIGIN,
            'DS': get_ds(self.DS_SALT),
            'x-rpc-app_version': self.APP_VERSION,
            'User-Agent': self.USER_AGENT,
            'x-rpc-client_type': '5',  # 1为ios 2为安卓 4为pc_web 5为mobile_web
            'Referer': self.REFERER,
            'x-rpc-device_id': get_device_id(self.USER_AGENT)}
        self.client = AsyncClient(headers=self.headers)

    async def is_sign(self, uid: int, region: str = "cn_gf01", cookies: dict = None):
        """
        检查是否签到
        :param uid: 游戏UID
        :param region: 服务器
        :param cookies: cookie
        :return:
        """
        params = {
            "act_id": self.ACT_ID,
            "region": region,
            "uid": uid
        }
        req = await self.client.get(self.SIGN_INFO_URL, params=params, cookies=cookies)
        if req.is_error:
            return BaseResponseData(error_message="请求错误")
        return BaseResponseData(req.json())

    async def sign(self, uid: int, region: str = "cn_gf01", cookies: dict = None):
        """
        执行签到
        :param uid: 游戏UID
        :param region: 服务器
        :param cookies: cookie
        :return:
        """
        data = {
            "act_id": self.ACT_ID,
            "region": region,
            "uid": uid
        }
        req = await self.client.post(self.SIGN_URL, json=data, cookies=cookies)
        if req.is_error:
            return BaseResponseData(error_message="签到失败")
        return BaseResponseData(req.json())

    async def get_sign_give(self, cookies: dict = None):
        """
        返回今日签到信息
        :param cookies:
        :return:
        """
        params = {
            "act_id": self.ACT_ID
        }
        req = await self.client.get(self.SIGN_HOME_URL, params=params, cookies=cookies)
        if req.is_error:
            return
        return BaseResponseData(req.json())

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.aclose()
