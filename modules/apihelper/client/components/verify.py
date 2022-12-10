import json
import re
import time
from typing import Dict, Optional

from ..base.hyperionrequest import HyperionRequest
from ...utility.helpers import get_ua, get_device_id, get_ds

__all__ = ("Verify",)


class Verify:
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
        self.client = HyperionRequest(headers=self.BBS_HEADERS, cookies=cookies)

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
