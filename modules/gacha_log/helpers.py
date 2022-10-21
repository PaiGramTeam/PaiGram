def from_url_get_authkey(url: str) -> str:
    """从 UEL 解析 authkey
    :param url: URL
    :return: authkey
    """
    try:
        return url.split("authkey=")[1].split("&")[0]
    except IndexError:
        return url
