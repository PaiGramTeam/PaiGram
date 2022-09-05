import hashlib
import random
import string
import time
import uuid

RECOGNIZE_SERVER = {
    "1": "cn_gf01",
    "2": "cn_gf01",
    "5": "cn_qd01",
    "6": "os_usa",
    "7": "os_euro",
    "8": "os_asia",
    "9": "os_cht",
}


def get_device_id(name: str) -> str:
    return str(uuid.uuid3(uuid.NAMESPACE_URL, name)).replace('-', '').upper()


def md5(text: str) -> str:
    _md5 = hashlib.md5(usedforsecurity=False)
    _md5.update(text.encode())
    return _md5.hexdigest()


def random_text(num: int) -> str:
    return ''.join(random.sample(string.ascii_lowercase + string.digits, num))


def timestamp() -> int:
    return int(time.time())


def get_ds(salt: str = "", web: int = 1) -> str:
    if salt == "":
        if web == 1:
            salt = "h8w582wxwgqvahcdkpvdhbh2w9casgfl"
        elif web == 2:
            salt = "h8w582wxwgqvahcdkpvdhbh2w9casgfl"
        elif web == 3:
            salt = "fd3ykrh7o1j54g581upo1tvpam0dsgtf"
    i = str(timestamp())
    r = random_text(6)
    c = md5("salt=" + salt + "&t=" + i + "&r=" + r)
    return f"{i},{r},{c}"


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
