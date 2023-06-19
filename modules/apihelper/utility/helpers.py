import hashlib
import json
import random
import string
import time
import uuid
from typing import Any, Mapping, Optional

__all__ = ("get_device_id", "hex_digest", "get_ds", "get_recognize_server", "get_ua")

RECOGNIZE_SERVER = {
    "1": "cn_gf01",
    "2": "cn_gf01",
    "5": "cn_qd01",
    "6": "os_usa",
    "7": "os_euro",
    "8": "os_asia",
    "9": "os_cht",
}


def get_device_id(name: str = ""):
    return str(uuid.uuid3(uuid.NAMESPACE_URL, name))


def hex_digest(text):
    _md5 = hashlib.md5()  # nosec B303
    _md5.update(text.encode())
    return _md5.hexdigest()


def get_ds(ds_type: str = None, new_ds: bool = False, data: Any = None, params: Optional[Mapping[str, Any]] = None):
    """DS 算法

    代码来自 https://github.com/y1ndan/genshinhelper
    :param ds_type:  1:ios  2:android  4:pc web  5:mobile web
    :param new_ds: 是否为DS2算法
    :param data: 需要签名的Data
    :param params: 需要签名的Params
    :return:
    """

    def new():
        t = str(int(time.time()))
        r = str(random.randint(100001, 200000))  # nosec
        b = json.dumps(data) if data else ""
        q = "&".join(f"{k}={v}" for k, v in sorted(params.items())) if params else ""
        c = hex_digest(f"salt={salt}&t={t}&r={r}&b={b}&q={q}")
        return f"{t},{r},{c}"

    def old():
        t = str(int(time.time()))
        r = "".join(random.sample(string.ascii_lowercase + string.digits, 6))
        c = hex_digest(f"salt={salt}&t={t}&r={r}")
        return f"{t},{r},{c}"

    app_version = "2.53.0"
    client_type = "5"
    salt = "0PUWkNIBnLcg8GgRNRJc14kSn4SrPBsS"
    ds = old()
    if ds_type in {"android", "2"}:
        client_type = "2"
        salt = "yuzHvf4MkGYyoS4837hHOwLMyVOmtPuY"
        ds = old()
    elif ds_type == "android_new":
        client_type = "2"
        salt = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"
        ds = new()
    if new_ds:
        client_type = "5"
        salt = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"
        ds = new()

    return app_version, client_type, ds


def get_recognize_server(uid: int) -> str:
    server = RECOGNIZE_SERVER.get(str(uid)[0])
    if server:
        return server
    raise TypeError(f"UID {uid} isn't associated with any recognize server")


def get_ua(device: str = "Paimon Build", version: str = "2.36.1"):
    return (
        f"Mozilla/5.0 (Linux; Android 12; {device}; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 "
        f"{'miHoYoBBS/' + version if version else ''}"
    )
