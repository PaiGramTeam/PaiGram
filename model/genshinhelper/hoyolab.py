from httpx import AsyncClient

from model.genshinhelper import BaseResponseData
from model.genshinhelper.helpers import get_ds, get_device_id, recognize_server


class Genshin:
    SIGN_INFO_URL = "https://hk4e-api-os.hoyoverse.com/event/sol/info"
    SIGN_URL = "https://hk4e-api-os.hoyoverse.com/event/sol/sign"
    SIGN_HOME_URL = "https://hk4e-api-os.hoyoverse.com/event/sol/home"

    APP_VERSION = "2.11.1"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " \
                 "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    REFERER = "https://webstatic.hoyoverse.com"
    ORIGIN = "https://webstatic.hoyoverse.com"

    ACT_ID = "e202102251931481"
    DS_SALT = "6cqshh5dhw73bzxn20oexa9k516chk7s"

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

    async def is_sign(self, uid: int, region: str = "", cookies: dict = None, lang: str = 'zh-cn'):
        """
        检查是否签到
        :param lang: 语言
        :param uid: 游戏UID
        :param region: 服务器
        :param cookies: cookie
        :return:
        """
        if region == "":
            region = recognize_server(uid)
        params = {
            "act_id": self.ACT_ID,
            "region": region,
            "uid": uid,
            "lang": lang
        }
        req = await self.client.get(self.SIGN_INFO_URL, params=params, cookies=cookies)
        if req.is_error:
            return BaseResponseData(error_message="请求错误")
        return BaseResponseData(req.json())

    async def sign(self, uid: int, region: str = "", cookies: dict = None, lang: str = 'zh-cn'):
        """
        执行签到
        :param lang:
        :param uid: 游戏UID
        :param region: 服务器
        :param cookies: cookie
        :return:
        """
        if region == "":
            region = recognize_server(uid)
        data = {
            "act_id": self.ACT_ID,
            "region": region,
            "uid": uid,
            "lang": lang
        }
        req = await self.client.post(self.SIGN_URL, json=data, cookies=cookies)
        if req.is_error:
            return BaseResponseData(error_message="签到失败")
        return BaseResponseData(req.json())

    async def get_sign_give(self, cookies: dict = None, lang: str = 'zh-cn'):
        """
        返回今日签到信息
        :param lang:
        :param cookies:
        :return:
        """
        params = {
            "act_id": self.ACT_ID,
            "lang": lang
        }
        req = await self.client.get(self.SIGN_HOME_URL, params=params, cookies=cookies)
        if req.is_error:
            return
        return BaseResponseData(req.json())

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.aclose()
