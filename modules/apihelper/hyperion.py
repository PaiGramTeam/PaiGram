import asyncio
import json
import re
import time
from datetime import datetime
from json import JSONDecodeError
from typing import List, Optional, Dict

from genshin import Client, InvalidCookies
from genshin.utility.ds import generate_dynamic_secret
from genshin.utility.uid import recognize_genshin_server
from httpx import AsyncClient
from pydantic import BaseModel, validator

from modules.apihelper.base import ArtworkImage, PostInfo
from modules.apihelper.helpers import get_device_id, get_ds, get_ua
from modules.apihelper.request.hoyorequest import HOYORequest
from utils.typedefs import JSONDict


class Hyperion:
    """米忽悠bbs相关API请求

    该名称来源于米忽悠的安卓BBS包名结尾，考虑到大部分重要的功能确实是在移动端实现了
    """

    POST_FULL_URL = "https://bbs-api.mihoyo.com/post/wapi/getPostFull"
    POST_FULL_IN_COLLECTION_URL = "https://bbs-api.mihoyo.com/post/wapi/getPostFullInCollection"
    GET_NEW_LIST_URL = "https://bbs-api.mihoyo.com/post/wapi/getNewsList"
    GET_OFFICIAL_RECOMMENDED_POSTS_URL = "https://bbs-api.mihoyo.com/post/wapi/getOfficialRecommendedPosts"

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

    async def get_official_recommended_posts(self, gids: int) -> JSONDict:
        params = {"gids": gids}
        response = await self.client.get(url=self.GET_OFFICIAL_RECOMMENDED_POSTS_URL, params=params)
        return response

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
        return ArtworkImage(art_id=art_id, page=page, data=response.content)

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


class GachaInfoObject(BaseModel):
    begin_time: datetime
    end_time: datetime
    gacha_id: str
    gacha_name: str
    gacha_type: int

    @validator("begin_time", "end_time", pre=True, allow_reuse=True)
    def validate_time(cls, v):
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")


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

    async def get_gacha_list_info(self) -> List[GachaInfoObject]:
        if self.cache.get("time", 0) + self.cache_ttl < time.time():
            self.cache.clear()
        cache = self.cache.get("gacha_list_info")
        if cache is not None:
            return cache
        req = await self.client.get(self.GACHA_LIST_URL)
        data = [GachaInfoObject(**i) for i in req["list"]]
        self.cache["gacha_list_info"] = data
        self.cache["time"] = time.time()
        return data

    async def get_gacha_info(self, gacha_id: str) -> dict:
        cache = self.cache.get(gacha_id)
        if cache is not None:
            return cache
        req = await self.client.get(self.GACHA_INFO_URL % gacha_id)
        self.cache[gacha_id] = req
        return req

    async def close(self):
        await self.client.shutdown()


class SignIn:
    LOGIN_URL = "https://webapi.account.mihoyo.com/Api/login_by_mobilecaptcha"
    S_TOKEN_URL = (
        "https://api-takumi.mihoyo.com/auth/api/getMultiTokenByLoginTicket?login_ticket={0}&token_types=3&uid={1}"
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
    AUTHKEY_API = "https://api-takumi.mihoyo.com/binding/api/genAuthKey"
    USER_INFO_API = "https://bbs-api.mihoyo.com/user/wapi/getUserFullInfo"
    GACHA_HEADERS = {
        "User-Agent": "okhttp/4.8.0",
        "x-rpc-app_version": "2.28.1",
        "x-rpc-sys_version": "12",
        "x-rpc-client_type": "5",
        "x-rpc-channel": "mihoyo",
        "x-rpc-device_id": get_device_id(USER_AGENT),
        "x-rpc-device_name": "Mi 10",
        "x-rpc-device_model": "Mi 10",
        "Referer": "https://app.mihoyo.com",
        "Host": "api-takumi.mihoyo.com",
    }

    def __init__(self, phone: int = 0, uid: int = 0, cookie: Dict = None):
        self.phone = phone
        self.client = AsyncClient()
        self.uid = uid
        self.cookie = cookie if cookie is not None else {}
        self.parse_uid()

    def parse_uid(self):
        """
        从cookie中获取uid
        :param self:
        :return:
        """
        if not self.cookie:
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

        if "login_ticket" not in self.cookie:
            return False
        self.parse_uid()
        return bool(self.uid)

    async def get_s_token(self):
        if not self.cookie.get("login_ticket") or not self.uid:
            return
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

        return "cookie_token" in self.cookie or "cookie_token_v2" in self.cookie

    @staticmethod
    async def get_authkey_by_stoken(client: Client) -> Optional[str]:
        """通过 stoken 获取 authkey"""
        try:
            headers = SignIn.GACHA_HEADERS.copy()
            headers["DS"] = generate_dynamic_secret("ulInCDohgEs557j0VsPDYnQaaz6KJcv5")
            data = await client.cookie_manager.request(
                SignIn.AUTHKEY_API,
                method="POST",
                json={
                    "auth_appid": "webview_gacha",
                    "game_biz": "hk4e_cn",
                    "game_uid": client.uid,
                    "region": recognize_genshin_server(client.uid),
                },
                headers=headers,
            )
            return data.get("authkey")
        except JSONDecodeError:
            pass
        except InvalidCookies:
            pass
        return None

    @staticmethod
    async def get_v2_account_id(client: Client) -> Optional[int]:
        """获取 v2 account_id"""
        try:
            headers = SignIn.GACHA_HEADERS.copy()
            headers["DS"] = generate_dynamic_secret("ulInCDohgEs557j0VsPDYnQaaz6KJcv5")
            data = await client.cookie_manager.request(
                SignIn.USER_INFO_API,
                method="GET",
                params={"gids": "2"},
                headers=headers,
            )
            uid = data.get("user_info", {}).get("uid", None)
            if uid:
                uid = int(uid)
            return uid
        except JSONDecodeError:
            pass
        except InvalidCookies:
            pass
        return None


class Verification:
    HOST = "api-takumi-record.mihoyo.com"
    VERIFICATION_HOST = "api.geetest.com"
    CREATE_VERIFICATION_URL = "/game_record/app/card/wapi/createVerification"
    VERIFY_VERIFICATION_URL = "/game_record/app/card/wapi/verifyVerification"
    AJAX_URL = "/ajax.php"

    USER_AGENT = get_ua()
    BBS_HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "User-Agent": USER_AGENT,
        "X-Requested-With": "com.mihoyo.hyperion",
        "Referer": "https://webstatic.mihoyo.com/",
        "x-rpc-device_id": get_device_id(USER_AGENT),
        "x-rpc-page": "3.1.3_#/ys",
    }

    VERIFICATION_HEADERS = {
        "Accept": "*/*",
        "X-Requested-With": "com.mihoyo.hyperion",
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(self, cookies: Dict = None):
        self.client = HOYORequest(headers=self.BBS_HEADERS, cookies=cookies)

    def get_verification_headers(self, referer: str):
        headers = self.VERIFICATION_HEADERS.copy()
        headers["Referer"] = referer
        return headers

    def get_headers(self, data: dict = None, params: dict = None):
        headers = self.BBS_HEADERS.copy()
        app_version, client_type, ds = get_ds(new_ds=True, data=data, params=params)
        headers["x-rpc-app_version"] = app_version
        headers["x-rpc-client_type"] = client_type
        headers["DS"] = ds
        return headers

    @staticmethod
    def get_url(host: str, url: str):
        return f"https://{host}{url}"

    async def create(self, is_high: bool = False):
        url = self.get_url(self.HOST, self.CREATE_VERIFICATION_URL)
        params = {"is_high": "true" if is_high else "false"}
        headers = self.get_headers(params=params)
        response = await self.client.get(url, params=params, headers=headers)
        return response

    async def verify(self, challenge: str, validate: str):
        url = self.get_url(self.HOST, self.VERIFY_VERIFICATION_URL)
        data = {"geetest_challenge": challenge, "geetest_validate": validate, "geetest_seccode": f"{validate}|jordan"}

        headers = self.get_headers(data=data)
        response = await self.client.post(url, json=data, headers=headers)
        return response

    async def ajax(self, referer: str, gt: str, challenge: str) -> Optional[str]:
        headers = self.get_verification_headers(referer)
        url = self.get_url(self.VERIFICATION_HOST, self.AJAX_URL)
        params = {
            "gt": gt,
            "challenge": challenge,
            "lang": "zh-cn",
            "pt": 3,
            "client_type": "web_mobile",
            "callback": f"geetest_{int(time.time() * 1000)}",
        }
        response = await self.client.get(url, headers=headers, params=params, de_json=False)
        text = response.text
        json_data = re.findall(r"^.*?\((\{.*?)\)$", text)[0]
        data = json.loads(json_data)
        if "success" in data["status"] and "success" in data["data"]["result"]:
            return data["data"]["validate"]
        return None
