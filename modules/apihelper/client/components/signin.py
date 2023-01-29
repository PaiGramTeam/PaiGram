import asyncio
import json
import random
import qrcode

from io import BytesIO
from string import ascii_letters, digits
from typing import Dict
from httpx import AsyncClient

from ...logger import logger
from ...utility.helpers import get_device_id, get_ds

__all__ = ("SignIn",)


# noinspection SpellCheckingInspection
class SignIn:
    S_TOKEN_URL = (
        "https://api-takumi.mihoyo.com/auth/api/getMultiTokenByLoginTicket?login_ticket={0}&token_types=3&uid={1}"
    )
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
    )
    QRCODE_GEN_API = "https://hk4e-sdk.mihoyo.com/hk4e_cn/combo/panda/qrcode/fetch"
    QRCODE_GET_API = "https://hk4e-sdk.mihoyo.com/hk4e_cn/combo/panda/qrcode/query"
    GAME_TOKEN_API = "https://api-takumi.mihoyo.com/auth/api/getCookieAccountInfoByGameToken"
    GAME_LTOKEN_API = "https://passport-api.mihoyo.com/account/ma-cn-session/app/getTokenByGameToken"

    def __init__(self, uid: int = 0, cookie: Dict = None):
        self.client = AsyncClient()
        self.uid = uid
        self.cookie = cookie if cookie is not None else {}
        self.parse_uid()
        self.ticket = None
        self.device_id = None

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

    async def get_ltoken_by_game_token(self, game_token: str):
        data = {"account_id": self.uid, "game_token": game_token}
        headers = {
            "x-rpc-aigis": "",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-rpc-game_biz": "bbs_cn",
            "x-rpc-sys_version": "11",
            "x-rpc-device_id": get_device_id(self.USER_AGENT),
            "x-rpc-device_fp": "".join(random.choices((ascii_letters + digits), k=13)),
            "x-rpc-device_name": "Chrome 108.0.0.0",
            "x-rpc-device_model": "Windows 10 64-bit",
            "x-rpc-app_id": "bll8iq97cem8",
            "User-Agent": "okhttp/4.8.0",
        }
        app_version, client_type, ds_sign = get_ds(new_ds=True, data=data)
        headers["x-rpc-app_version"] = app_version
        headers["x-rpc-client_type"] = client_type
        headers["DS"] = ds_sign
        res = await self.client.post(
            self.GAME_LTOKEN_API,
            headers=headers,
            json={"account_id": self.uid, "game_token": game_token},
        )
        return res.json()

    async def create_login_data(self) -> str:
        self.device_id = get_device_id("".join(random.choices((ascii_letters + digits), k=64)))
        data = {"app_id": "4", "device": self.device_id}
        res = await self.client.post(self.QRCODE_GEN_API, json=data)
        res_json = res.json()
        url = res_json.get("data", {}).get("url", "")
        if not url:
            return ""
        self.ticket = url.split("ticket=")[1]
        return url

    async def get_cookie_token_data(self, game_token: str) -> Dict:
        res = await self.client.get(
            self.GAME_TOKEN_API,
            params={"game_token": game_token, "account_id": self.uid},
        )
        return res.json()

    async def set_cookie(self, data: Dict) -> bool:
        self.cookie = {}
        game_token = json.loads(data.get("payload", {}).get("raw", "{}"))
        if not game_token:
            return False
        self.uid = int(game_token["uid"])
        for item in ["login_uid", "stuid", "ltuid", "account_id"]:
            self.cookie[item] = str(self.uid)
        cookie_token_data = await self.get_cookie_token_data(game_token["token"])
        ltoken_data = await self.get_ltoken_by_game_token(game_token["token"])
        self.cookie["cookie_token"] = cookie_token_data["data"]["cookie_token"]
        for item in ["account_mid_v2", "ltmid_v2"]:
            self.cookie[item] = ltoken_data["data"]["user_info"]["mid"]
        self.cookie["ltoken_v2"] = ltoken_data["data"]["token"]["token"]
        return True

    async def check_login(self):
        data = {"app_id": "4", "ticket": self.ticket, "device": self.device_id}
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
                return await self.set_cookie(res_json.get("data", {}))

    @staticmethod
    def generate_qrcode(url: str) -> bytes:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = BytesIO()
        img.save(bio, format="PNG")
        return bio.getvalue()
