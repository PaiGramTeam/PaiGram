from typing import Union


class PlayerCardsError(Exception):
    """本模块的异常基本类型"""
    pass


class ResponseError(PlayerCardsError):
    """请求错误"""
    def __init__(self, status_code):
        super().__init__(f"请求错误 status_code[{status_code}] ")


class PlayerInfoDataNotFind(PlayerCardsError):
    def __init__(self, uid: Union[str, int]):
        super().__init__(f"请求 UID[{uid}] 的角色展柜信息不全")


class ShowAvatarInfoNotFind(PlayerCardsError):
    def __init__(self, uid: Union[str, int]):
        super().__init__(f"UID[{uid}] 的角色展柜内还没有角色")


class AvatarInfoNotFind(PlayerCardsError):
    def __init__(self, uid: Union[str, int]):
        super().__init__(f"UID[{uid}] 的角色展柜详细数据已隐藏")
