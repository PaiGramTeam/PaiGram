from typing import Optional

from genshin import Client
from genshin.client.routes import InternationalRoute  # noqa F401
from genshin.utility import recognize_genshin_server

from modules.apihelper.utility.devices import devices_methods
from modules.apihelper.utility.helpers import hex_digest, get_ds

AUTHKEY_API = "https://api-takumi.mihoyo.com/binding/api/genAuthKey"
HK4E_LOGIN_URL = InternationalRoute(
    overseas="https://sg-public-api.hoyoverse.com/common/badge/v1/login/account",
    chinese="https://api-takumi.mihoyo.com/common/badge/v1/login/account",
)
GACHA_HEADERS = {
    "User-Agent": "okhttp/4.8.0",
    "x-rpc-sys_version": "12",
    "x-rpc-channel": "mihoyo",
    "x-rpc-device_name": "",
    "x-rpc-device_model": "",
    "Referer": "https://app.mihoyo.com",
    "Host": "api-takumi.mihoyo.com",
}


def recognize_genshin_game_biz(game_uid: int) -> str:
    return "hk4e_cn" if game_uid < 600000000 else "hk4e_global"


async def get_authkey_by_stoken(client: Client, auth_appid: str = "webview_gacha") -> Optional[str]:
    """通过 stoken 获取 authkey"""
    headers = GACHA_HEADERS.copy()
    json = {
        "auth_appid": auth_appid,
        "game_biz": recognize_genshin_game_biz(client.uid),
        "game_uid": client.uid,
        "region": recognize_genshin_server(client.uid),
    }
    device_id = hex_digest(str(client.uid))
    device = f"Paimon Build {device_id[:5]}"
    await devices_methods.update_device_headers(client.hoyolab_id, headers)
    headers["x-rpc-device_name"] = device
    headers["x-rpc-device_model"] = device
    app_version, client_type, ds_sign = get_ds()
    headers["x-rpc-app_version"] = app_version
    headers["x-rpc-client_type"] = client_type
    headers["ds"] = ds_sign
    data = await client.cookie_manager.request(AUTHKEY_API, method="POST", json=json, headers=headers)
    return data.get("authkey")


async def fetch_hk4e_token_by_cookie(client: Client) -> None:
    """通过 cookie_token 获取 hk4e_token 保存到 client"""
    url = HK4E_LOGIN_URL.get_url(client.region)
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
    }
    json = {
        "game_biz": recognize_genshin_game_biz(client.uid),
        "lang": "zh-cn",
        "uid": str(client.uid),
        "region": recognize_genshin_server(client.uid),
    }
    await client.cookie_manager.request(url, method="POST", json=json, headers=headers)
