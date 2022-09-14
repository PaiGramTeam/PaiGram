import asyncio
import re
from typing import List

import httpx
from httpx import AsyncClient

from modules.apihelper.base import HyperionResponse, ArtworkImage, BaseResponseData
from modules.apihelper.helpers import get_ds, get_device_id


class Hyperion:
    """
    米忽悠bbs相关API请求
    该名称来源于米忽悠的安卓BBS包名结尾，考虑到大部分重要的功能确实是在移动端实现了
    """

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
        rgx = re.compile(r"(?:bbs\.)?mihoyo\.com/[^.]+/article/(?P<article_id>\d+)")
        matches = rgx.search(text)
        if matches is None:
            return -1
        entries = matches.groupdict()
        if entries is None:
            return -1
        try:
            art_id = int(entries.get('article_id'))
        except (IndexError, ValueError, TypeError):
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

    async def get_artwork_info(self, gids: int, post_id: int, read: int = 1) -> HyperionResponse:
        params = {
            "gids": gids,
            "post_id": post_id,
            "read": read
        }
        response = await self.client.get(self.POST_FULL_URL, params=params)
        if response.is_error:
            return HyperionResponse(error_message="请求错误")
        return HyperionResponse(response.json())

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
              "bbs_auth_required=true&act_id=e202009291139501&utm_source=hyperion&utm_medium=mys&utm_campaign=icon"
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
        """
        :return:
        """
        pass

    async def __aexit__(self, exc_type, exc, tb):
        """
        :param exc_type:
        :param exc:
        :param tb:
        :return:
        """
        await self.client.aclose()

    class SignIn:
        LOGIN_URL = "https://webapi.account.mihoyo.com/Api/login_by_mobilecaptcha"
        S_TOKEN_URL = "https://api-takumi.mihoyo.com/auth/api/getMultiTokenByLoginTicket?" \
                      "login_ticket={0}&token_types=3&uid={1}"
        BBS_URL = "https://api-takumi.mihoyo.com/account/auth/api/webLoginByMobile"
        USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " \
                     "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
        HEADERS = {
            "Host": "webapi.account.mihoyo.com",
            "Connection": "keep-alive",
            "sec-ch-ua": "\".Not/A)Brand\";v=\"99\", \"Microsoft Edge\";v=\"103\", \"Chromium\";v=\"103\"",
            "DNT": "1",
            "x-rpc-device_model": "OS X 10.15.7",
            "sec-ch-ua-mobile": "?0",
            "User-Agent": USER_AGENT,
            'x-rpc-device_id': get_device_id(USER_AGENT),
            "Accept": "application/json, text/plain, */*",
            "x-rpc-device_name": "Microsoft Edge 103.0.1264.62",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-rpc-client_type": "4",
            "sec-ch-ua-platform": "\"macOS\"",
            "Origin": "https://user.mihoyo.com",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://user.mihoyo.com/",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"
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
            "Accept-Language": "zh-CN,zh-Hans;q=0.9"
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
                headers=self.HEADERS
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
                self.S_TOKEN_URL.format(self.cookie["login_ticket"], self.uid),
                headers={"User-Agent": self.USER_AGENT}
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
                    "token_type": 6
                }
            )
            res_json = data.json()
            if self.check_error(res_json):
                return False

            for k, v in data.cookies.items():
                self.cookie[k] = v

            return "cookie_token" in self.cookie
