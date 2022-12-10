from typing import Optional

from genshin import Client
from genshin.utility import recognize_genshin_server

AUTHKEY_API = "https://api-takumi.mihoyo.com/binding/api/genAuthKey"


async def get_authkey_by_stoken(client: Client) -> Optional[str]:
    """通过 stoken 获取 authkey"""
    json = {
        "auth_appid": "webview_gacha",
        "game_biz": "hk4e_cn",
        "game_uid": client.uid,
        "region": recognize_genshin_server(client.uid),
    }
    data = await client.request_bbs(AUTHKEY_API, method="POST", data=json)
    return data.get("authkey")
