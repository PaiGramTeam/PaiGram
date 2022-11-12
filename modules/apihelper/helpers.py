import hashlib
import json
import random
import string
import time
import uuid
from typing import Mapping
from urllib.parse import urlencode

RECOGNIZE_SERVER = {
    "1": "cn_gf01",
    "2": "cn_gf01",
    "5": "cn_qd01",
    "6": "os_usa",
    "7": "os_euro",
    "8": "os_asia",
    "9": "os_cht",
}


def get_device_id(name: str = None):
    return str(uuid.uuid3(uuid.NAMESPACE_URL, name))


def random_text(num: int) -> str:
    return "".join(random.sample(string.ascii_lowercase + string.digits, num))


def timestamp() -> int:
    return int(time.time())


def _hexdigest(text):
    _md5 = hashlib.md5()  # nosec B303
    _md5.update(text.encode())
    return _md5.hexdigest()


def get_ds(ds_type: str = None, new_ds: bool = False, data: Mapping[str, str] = None, params: Mapping[str, str] = None):
    # 1:  ios
    # 2:  android
    # 4:  pc web
    # 5:  mobile web
    def new():
        t = str(int(time.time()))
        r = str(random.randint(100001, 200000))
        b = json.dumps(data) if data else ''
        q = urlencode(params) if params else ''
        c = _hexdigest(f'salt={salt}&t={t}&r={r}&b={b}&q={q}')
        return f'{t},{r},{c}'

    def old():
        t = str(int(time.time()))
        r = ''.join(random.sample(string.ascii_lowercase + string.digits, 6))
        c = _hexdigest(f'salt={salt}&t={t}&r={r}')
        return f'{t},{r},{c}'

    app_version = '2.36.1'
    client_type = '5'
    salt = 'YVEIkzDFNHLeKXLxzqCA9TzxCpWwbIbk'
    ds = old()
    if ds_type == '2' or ds_type == 'android':
        app_version = '2.36.1'
        client_type = '2'
        salt = 'n0KjuIrKgLHh08LWSCYP0WXlVXaYvV64'
        ds = old()
    if ds_type == 'android_new':
        app_version = '2.36.1'
        client_type = '2'
        salt = 't0qEgfub6cvueAPgR5m9aQWWVciEer7v'
        ds = new()
    if new_ds:
        app_version = '2.36.1'
        client_type = '5'
        salt = 'xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs'
        ds = new()

    return app_version, client_type, ds


def get_recognize_server(uid: int) -> str:
    server = RECOGNIZE_SERVER.get(str(uid)[0])
    if server:
        return server
    else:
        raise TypeError(f"UID {uid} isn't associated with any recognize server")


def get_headers():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.63 Safari/537.36",
    }
    return headers
