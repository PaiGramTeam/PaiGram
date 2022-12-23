from typing import Optional

from genshin import Client
from genshin.utility import recognize_genshin_server

from modules.apihelper.utility.helpers import hex_digest, get_ds

AUTHKEY_API = "https://api-takumi.mihoyo.com/binding/api/genAuthKey"
GACHA_HEADERS = {
    "User-Agent": "okhttp/4.8.0",
    "x-rpc-sys_version": "12",
    "x-rpc-channel": "mihoyo",
    "x-rpc-device_id": "",
    "x-rpc-device_name": "",
    "x-rpc-device_model": "",
    "Referer": "https://app.mihoyo.com",
    "Host": "api-takumi.mihoyo.com",
}


async def get_authkey_by_stoken(client: Client) -> Optional[str]:
    """通过 stoken 获取 authkey"""
    headers = GACHA_HEADERS.copy()
    json = {
        "auth_appid": "webview_gacha",
        "game_biz": "hk4e_cn",
        "game_uid": client.uid,
        "region": recognize_genshin_server(client.uid),
    }
    device_id = hex_digest(str(client.uid))
    headers["x-rpc-device_id"] = device_id
    device = "Paimon Build " + device_id[0:5]
    headers["x-rpc-device_name"] = device
    headers["x-rpc-device_model"] = device
    app_version, client_type, ds_sign = get_ds()
    headers["x-rpc-app_version"] = app_version
    headers["x-rpc-client_type"] = client_type
    headers["ds"] = ds_sign
    data = await client.cookie_manager.request(AUTHKEY_API, method="POST", json=json, headers=headers)
    return data.get("authkey")
