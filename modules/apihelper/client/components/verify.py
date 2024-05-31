import json
import re
import time
from typing import Dict, Optional, Union

from httpx import Cookies
from simnet import Region
from simnet.utils.ds import generate_dynamic_secret

from ..base.hyperionrequest import HyperionRequest
from ...utility.devices import devices_methods
from ...utility.helpers import get_ua

__all__ = ("Verify",)


class Verify:
    HOST = "api-takumi-record.mihoyo.com"
    HOST_OVER = "sg-public-api.hoyolab.com"
    VERIFICATION_HOST = "api.geetest.com"
    CREATE_VERIFICATION_URL = "/game_record/app/card/wapi/createVerification"
    VERIFY_VERIFICATION_URL = "/game_record/app/card/wapi/verifyVerification"
    CREATE_VERIFICATION_URL1 = "/event/toolcomsrv/risk/createGeetest"
    VERIFY_VERIFICATION_URL1 = "/event/toolcomsrv/risk/verifyGeetest"
    REFERER_URL = "https://api-takumi-record.mihoyo.com/game_record/app/genshin/api/dailyNote"
    REFERER_URL1 = "https://bbs-api-os.hoyolab.com/game_record/app/genshin/api/dailyNote"
    APP_KEY = "hk4e_game_record"
    GAME = "2"
    AJAX_URL = "/ajax.php"

    def __init__(self, account_id: int = None, cookies: Union[Dict, Cookies] = None, region: Region = Region.CHINESE):
        self.account_id = account_id
        self.region = region
        self.client = HyperionRequest(headers=self.get_bbs_headers(), cookies=cookies)

    @property
    def create_url(self) -> str:
        return (
            self.get_url(self.HOST, self.CREATE_VERIFICATION_URL)
            if self.miyoushe
            else self.get_url(self.HOST_OVER, self.CREATE_VERIFICATION_URL1)
        )

    @property
    def verify_url(self) -> str:
        return (
            self.get_url(self.HOST, self.VERIFY_VERIFICATION_URL)
            if self.miyoushe
            else self.get_url(self.HOST_OVER, self.VERIFY_VERIFICATION_URL1)
        )

    @property
    def referer(self) -> str:
        return self.REFERER_URL if self.miyoushe else self.REFERER_URL1

    def get_ua(self, device: str = "Paimon Build"):
        return (
            f"Mozilla/5.0 (Linux; Android 12; {device}; wv) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 "
            f"{'miHoYoBBS/' if self.miyoushe else 'miHoYoBBSOversea/2.55.0'}"
        )

    @property
    def miyoushe(self) -> bool:
        return self.region == Region.CHINESE

    def get_bbs_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": get_ua(),
            "X-Requested-With": "com.mihoyo.hyperion" if self.miyoushe else "com.mihoyo.hoyolab",
            "Referer": "https://webstatic.mihoyo.com/" if self.miyoushe else "https://act.hoyolab.com/",
            "x-rpc-page": "3.1.3_#/rpg",
        }

    def get_verification_headers(self, referer: str):
        headers = {
            "Accept": "*/*",
            "X-Requested-With": "com.mihoyo.hyperion" if self.miyoushe else "com.mihoyo.hoyolab",
            "User-Agent": get_ua(),
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": referer,
        }
        return headers

    async def get_headers(self, data: dict = None, params: dict = None):
        headers = self.get_bbs_headers()
        app_version, client_type, ds = generate_dynamic_secret(
            region=self.region,
            new_ds=self.miyoushe,
            data=data,
            params=params,
        )
        headers["x-rpc-app_version"] = app_version
        headers["x-rpc-client_type"] = client_type
        headers["DS"] = ds
        headers["x-rpc-challenge_path"] = self.referer
        headers["x-rpc-challenge_game"] = self.GAME
        if not self.miyoushe:
            headers["origin"] = "https://act.hoyolab.com"
            headers["x-rpc-platform"] = "4"
            headers["x-rpc-language"] = "zh-cn"
            headers["x-rpc-challenge_trace"] = "undefined"
        await devices_methods.update_device_headers(self.account_id, headers)
        return headers

    @staticmethod
    def get_url(host: str, url: str):
        return f"https://{host}{url}"

    async def create(self, is_high: bool = False):
        url = self.create_url
        params = {"is_high": "true" if is_high else "false"}
        if not self.miyoushe:
            params["app_key"] = self.APP_KEY

        headers = await self.get_headers(params=params)
        response = await self.client.get(url, params=params, headers=headers)
        return response

    async def verify(self, challenge: str, validate: str):
        url = self.verify_url
        data = {"geetest_challenge": challenge, "geetest_validate": validate, "geetest_seccode": f"{validate}|jordan"}
        if not self.miyoushe:
            data["app_key"] = self.APP_KEY

        headers = await self.get_headers(data=data)
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
