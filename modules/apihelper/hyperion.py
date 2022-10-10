import asyncio
import re
import time
from typing import List

from httpx import AsyncClient

from modules.apihelper.base import ArtworkImage, PostInfo
from modules.apihelper.helpers import get_device_id
from modules.apihelper.request.hoyorequest import HOYORequest
from utils.typedefs import JSONDict


class Hyperion:
    """米忽悠bbs相关API请求

    该名称来源于米忽悠的安卓BBS包名结尾，考虑到大部分重要的功能确实是在移动端实现了
    """

    POST_FULL_URL = "https://bbs-api.mihoyo.com/post/wapi/getPostFull"
    POST_FULL_IN_COLLECTION_URL = "https://bbs-api.mihoyo.com/post/wapi/getPostFullInCollection"
    GET_NEW_LIST_URL = "https://bbs-api.mihoyo.com/post/wapi/getNewsList"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.72 Safari/537.36"
    )

    def __init__(self):
        self.client = HOYORequest(headers=self.get_headers())

    @staticmethod
    def extract_post_id(text: str) -> int:
        """
        :param text:
            # https://bbs.mihoyo.com/ys/article/8808224
            # https://m.bbs.mihoyo.com/ys/article/8808224
        :return: post_id
        """
        rgx = re.compile(r"(?:bbs\.)?mihoyo\.com/[^.]+/article/(?P<article_id>\d+)")
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

    def get_headers(self, referer: str = "https://bbs.mihoyo.com/"):
        return {"User-Agent": self.USER_AGENT, "Referer": referer}

    @staticmethod
    def get_list_url_params(forum_id: int, is_good: bool = False, is_hot: bool = False, page_size: int = 20) -> dict:
        params = {
            "forum_id": forum_id,
            "gids": 2,
            "is_good": is_good,
            "is_hot": is_hot,
            "page_size": page_size,
            "sort_type": 1,
        }

        return params

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

    async def get_post_full_in_collection(self, collection_id: int, gids: int = 2, order_type=1) -> JSONDict:
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
        result_list = await asyncio.gather(*task_list)
        for result in result_list:
            if isinstance(result, ArtworkImage):
                art_list.append(result)

        def take_page(elem: ArtworkImage):
            return elem.page

        art_list.sort(key=take_page)
        return art_list

    async def download_image(self, art_id: int, url: str, page: int = 0) -> ArtworkImage:
        response = await self.client.get(url, params=self.get_images_params(resize=2000), timeout=10, de_json=False)
        return ArtworkImage(art_id=art_id, page=page, data=response)

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


class GachaInfo:
    GACHA_LIST_URL = "https://webstatic.mihoyo.com/hk4e/gacha_info/cn_gf01/gacha/list.json"
    GACHA_INFO_URL = "https://webstatic.mihoyo.com/hk4e/gacha_info/cn_gf01/%s/zh-cn.json"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.72 Safari/537.36"
    )

    def __init__(self):
        self.headers = {
            "User-Agent": self.USER_AGENT,
        }
        self.client = HOYORequest(headers=self.headers)
        self.cache = {}
        self.cache_ttl = 600

    async def get_gacha_list_info(self) -> dict:
        if self.cache.get("time", 0) + self.cache_ttl < time.time():
            self.cache.clear()
        cache = self.cache.get("gacha_list_info")
        if cache is not None:
            return cache
        req = await self.client.get(self.GACHA_LIST_URL)
        self.cache["gacha_list_info"] = req
        self.cache["time"] = time.time()
        return req

    async def get_gacha_info(self, gacha_id: str) -> dict:
        cache = self.cache.get(gacha_id)
        if cache is not None:
            return cache
        req = await self.client.get(self.GACHA_INFO_URL % gacha_id)
        self.cache[gacha_id] = req
        return req


class SignIn:
    LOGIN_URL = "https://webapi.account.mihoyo.com/Api/login_by_mobilecaptcha"
    S_TOKEN_URL = (
        "https://api-takumi.mihoyo.com/auth/api/getMultiTokenByLoginTicket?" "login_ticket={0}&token_types=3&uid={1}"
    )
    BBS_URL = "https://api-takumi.mihoyo.com/account/auth/api/webLoginByMobile"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
    )
    HEADERS = {
        "Host": "webapi.account.mihoyo.com",
        "Connection": "keep-alive",
        "sec-ch-ua": '".Not/A)Brand";v="99", "Microsoft Edge";v="103", "Chromium";v="103"',
        "DNT": "1",
        "x-rpc-device_model": "OS X 10.15.7",
        "sec-ch-ua-mobile": "?0",
        "User-Agent": USER_AGENT,
        "x-rpc-device_id": get_device_id(USER_AGENT),
        "Accept": "application/json, text/plain, */*",
        "x-rpc-device_name": "Microsoft Edge 103.0.1264.62",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-rpc-client_type": "4",
        "sec-ch-ua-platform": '"macOS"',
        "Origin": "https://user.mihoyo.com",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://user.mihoyo.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    }
    BBS_HEADERS = {
        "Host": "api-takumi.mihoyo.com",
        "Content-Type": "application/json;charset=utf-8",
        "Origin": "https://bbs.mihoyo.com",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": USER_AGENT,
        "Referer": "https://bbs.mihoyo.com/",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    }

    def __init__(self, phone: int):
        self.phone = phone
        self.client = AsyncClient()
        self.uid = 0
        self.cookie = {}

    def parse_uid(self):
        """
        从cookie中获取uid
        :param self:
        :return:
        """
        if "login_ticket" not in self.cookie:
            return
        for item in ["login_uid", "stuid", "ltuid", "account_id"]:
            if item in self.cookie:
                self.uid = self.cookie[item]
                break
        for item in ["login_uid", "stuid", "ltuid", "account_id"]:
            self.cookie[item] = self.uid

    @staticmethod
    def check_error(data: dict) -> bool:
        """
        检查是否有错误
        :param data:
        :return:
        """
        res_data = data.get("data", {})
        return res_data.get("msg") == "验证码错误" or res_data.get("info") == "Captcha not match Err"

    async def login(self, captcha: int) -> bool:
        data = await self.client.post(
            self.LOGIN_URL,
            data={"mobile": str(self.phone), "mobile_captcha": str(captcha), "source": "user.mihoyo.com"},
            headers=self.HEADERS,
        )
        res_json = data.json()
        if self.check_error(res_json):
            return False

        for k, v in data.cookies.items():
            self.cookie[k] = v

        self.parse_uid()
        return bool(self.uid)

    async def get_s_token(self):
        data = await self.client.get(
            self.S_TOKEN_URL.format(self.cookie["login_ticket"], self.uid), headers={"User-Agent": self.USER_AGENT}
        )
        res_json = data.json()
        res_data = res_json.get("data", {}).get("list", [])
        for i in res_data:
            if i.get("name") and i.get("token"):
                self.cookie[i.get("name")] = i.get("token")

    async def get_token(self, captcha: int) -> bool:
        data = await self.client.post(
            self.BBS_URL,
            headers=self.BBS_HEADERS,
            json={
                "is_bh2": False,
                "mobile": str(self.phone),
                "captcha": str(captcha),
                "action_type": "login",
                "token_type": 6,
            },
        )
        res_json = data.json()
        if self.check_error(res_json):
            return False

        for k, v in data.cookies.items():
            self.cookie[k] = v

        return "cookie_token" in self.cookie
