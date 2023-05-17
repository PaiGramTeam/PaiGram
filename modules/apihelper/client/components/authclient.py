import asyncio
import json
import random
import qrcode

from io import BytesIO
from string import ascii_letters, digits
from typing import Dict, Union, Optional
from httpx import AsyncClient
from qrcode.image.pure import PyPNGImage

from ...logger import logger
from ...models.genshin.cookies import CookiesModel
from ...utility.helpers import get_device_id, get_ds, update_device_headers

__all__ = ("AuthClient",)


class AuthClient:
    player_id: Optional[int] = None
    user_id: Optional[int] = None
    cookies: Optional[CookiesModel] = None
    device_id: Optional[str] = None

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
    )
    PASSPORT_HOST = "passport-api.mihoyo.com"
    HK4E_SDK_HOST = "hk4e-sdk.mihoyo.com"
    TAKUMI_HOST = "api-takumi.mihoyo.com"
    QRCODE_GEN_API = f"https://{HK4E_SDK_HOST}/hk4e_cn/combo/panda/qrcode/fetch"
    QRCODE_GET_API = f"https://{HK4E_SDK_HOST}/hk4e_cn/combo/panda/qrcode/query"
    GET_COOKIE_ACCOUNT_BY_GAME_TOKEN_API = f"https://{TAKUMI_HOST}/auth/api/getCookieAccountInfoByGameToken"
    GET_TOKEN_BY_GAME_LTOKEN_API = f"https://{PASSPORT_HOST}/account/ma-cn-session/app/getTokenByGameToken"
    GET_COOKIES_TOKEN_BY_STOKEN_API = f"https://{PASSPORT_HOST}/account/auth/api/getCookieAccountInfoBySToken"
    GET_LTOKEN_BY_STOKEN_API = f"https://{PASSPORT_HOST}/account/auth/api/getLTokenBySToken"
    get_STOKEN_URL = f"https://{TAKUMI_HOST}/auth/api/getMultiTokenByLoginTicket"

    def __init__(
        self,
        player_id: Optional[int] = None,
        user_id: Optional[int] = None,
        cookies: Optional[Union[CookiesModel, dict]] = None,
    ):
        self.client = AsyncClient()
        self.player_id = player_id
        if cookies is None:
            self.cookies = CookiesModel()
        else:
            if isinstance(cookies, dict):
                self.cookies = CookiesModel(**cookies)
            elif isinstance(cookies, CookiesModel):
                self.cookies = cookies
            else:
                raise RuntimeError
        if user_id:
            self.user_id = user_id
        else:
            self.user_id = self.cookies.user_id

    async def get_stoken_by_login_ticket(self) -> bool:
        if self.cookies.login_ticket is None and self.user_id is None:
            return False
        params = {"login_ticket": self.cookies.login_ticket, "uid": self.user_id, "token_types": 3}
        data = await self.client.get(self.get_STOKEN_URL, params=params, headers={"User-Agent": self.USER_AGENT})
        res_json = data.json()
        res_data = res_json.get("data", {}).get("list", [])
        for i in res_data:
            name = i.get("name")
            token = i.get("token")
            if name and token and hasattr(self.cookies, name):
                setattr(self.cookies, name, token)
        if self.cookies.stoken:
            if self.cookies.stuid:
                self.cookies.stuid = self.user_id
            return True
        return False

    async def get_ltoken_by_game_token(self, game_token: str) -> bool:
        if self.user_id is None:
            return False
        data = {"account_id": self.user_id, "game_token": game_token}
        headers = {
            "x-rpc-aigis": "",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-rpc-game_biz": "bbs_cn",
            "x-rpc-sys_version": "11",
            "x-rpc-device_name": "Chrome 108.0.0.0",
            "x-rpc-device_model": "Windows 10 64-bit",
            "x-rpc-app_id": "bll8iq97cem8",
            "User-Agent": "okhttp/4.8.0",
        }
        update_device_headers(self.user_id, headers)
        app_version, client_type, ds_sign = get_ds(new_ds=True, data=data)
        headers["x-rpc-app_version"] = app_version
        headers["x-rpc-client_type"] = client_type
        headers["DS"] = ds_sign
        res = await self.client.post(
            self.GET_TOKEN_BY_GAME_LTOKEN_API,
            headers=headers,
            json={"account_id": self.user_id, "game_token": game_token},
        )
        ltoken_data = res.json()
        self.cookies.ltmid_v2 = ltoken_data["data"]["user_info"]["mid"]
        self.cookies.ltoken_v2 = ltoken_data["data"]["token"]["token"]
        return True

    async def create_qrcode_login(self) -> tuple[str, str]:
        self.device_id = get_device_id("".join(random.choices((ascii_letters + digits), k=64)))
        data = {"app_id": "8", "device": self.device_id}
        res = await self.client.post(self.QRCODE_GEN_API, json=data)
        res_json = res.json()
        url = res_json.get("data", {}).get("url", "")
        if not url:
            return "", ""
        ticket = url.split("ticket=")[1]
        return url, ticket

    async def _get_cookie_token_data(self, game_token: str, account_id: int) -> Dict:
        res = await self.client.get(
            self.GET_COOKIE_ACCOUNT_BY_GAME_TOKEN_API,
            params={"game_token": game_token, "account_id": account_id},
        )
        return res.json()

    async def _set_cookie_by_game_token(self, data: Dict) -> bool:
        game_token = json.loads(data.get("payload", {}).get("raw", "{}"))
        if not game_token:
            return False
        uid = game_token["uid"]
        self.user_id = int(uid)
        cookie_token_data = await self._get_cookie_token_data(game_token["token"], self.user_id)
        await self.get_ltoken_by_game_token(game_token["token"])
        cookie_token = cookie_token_data["data"]["cookie_token"]
        self.cookies.cookie_token = cookie_token
        self.cookies.account_id = game_token["uid"]
        return True

    async def check_qrcode_login(self, ticket: str):
        data = {"app_id": "8", "ticket": ticket, "device": self.device_id}
        for _ in range(20):
            await asyncio.sleep(10)
            res = await self.client.post(self.QRCODE_GET_API, json=data)
            res_json = res.json()
            ret_code = res_json.get("retcode", 1)
            if ret_code != 0:
                logger.debug("QRCODE_GET_API: [%s]%s", res_json.get("retcode"), res_json.get("message"))
                return False
            logger.debug("QRCODE_GET_API: %s", res_json.get("data"))
            res_data = res_json.get("data", {})
            if res_data.get("stat", "") == "Confirmed":
                return await self._set_cookie_by_game_token(res_json.get("data", {}))

    async def get_cookie_token_by_stoken(self) -> bool:
        if self.cookies.stoken is None:
            return False
        user_id = self.cookies.user_id
        headers = {
            "x-rpc-app_version": "2.11.1",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) miHoYoBBS/2.11.1"
            ),
            "x-rpc-client_type": "5",
            "Referer": "https://webstatic.mihoyo.com/",
            "Origin": "https://webstatic.mihoyo.com",
        }
        params = {
            "stoken": self.cookies.stoken,
            "uid": user_id,
        }
        res = await self.client.get(
            self.GET_COOKIES_TOKEN_BY_STOKEN_API,
            headers=headers,
            params=params,
        )
        res_json = res.json()
        cookie_token = res_json.get("data", {}).get("cookie_token", "")
        if cookie_token:
            self.cookies.cookie_token = cookie_token
            self.cookies.account_id = user_id
            return True
        return False

    async def get_ltoken_by_stoken(self) -> bool:
        if self.cookies.stoken is None:
            return False
        user_id = self.cookies.user_id
        headers = {
            "x-rpc-app_version": "2.11.1",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) miHoYoBBS/2.11.1"
            ),
            "x-rpc-client_type": "5",
            "Referer": "https://webstatic.mihoyo.com/",
            "Origin": "https://webstatic.mihoyo.com",
        }
        params = {
            "stoken": self.cookies.stoken,
            "uid": user_id,
        }
        res = await self.client.get(
            self.GET_LTOKEN_BY_STOKEN_API,
            headers=headers,
            params=params,
        )
        res_json = res.json()
        ltoken = res_json.get("data", {}).get("ltoken", "")
        if ltoken:
            self.cookies.ltoken = ltoken
            self.cookies.ltuid = user_id
            return True
        return False

    @staticmethod
    def generate_qrcode(url: str) -> bytes:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(image_factory=PyPNGImage, fill_color="black", back_color="white")
        bio = BytesIO()
        img.save(bio)
        return bio.getvalue()
