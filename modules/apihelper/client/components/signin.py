from typing import Dict

from httpx import AsyncClient

from ...utility.helpers import get_device_id

__all__ = ("SignIn",)


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
