import imghdr
from enum import Enum
from typing import Union

from model.baseobject import BaseObject


class Stat:
    def __init__(self, view_num: int = 0, reply_num: int = 0, like_num: int = 0, bookmark_num: int = 0,
                 forward_num: int = 0):
        self.forward_num = forward_num  # 关注数
        self.bookmark_num = bookmark_num  # 收藏数
        self.like_num = like_num  # 喜欢数
        self.reply_num = reply_num  # 回复数
        self.view_num = view_num  # 观看数


class ArtworkInfo:

    def __init__(self):
        self.user_id: int = 0
        self.artwork_id: int = 0  # 作品ID
        self.site = ""
        self.title: str = ""  # 标题
        self.origin_url: str = ""
        self.site_name: str = ""
        self.tags: list = []
        self.stat: Stat = Stat()
        self.create_timestamp: int = 0
        self.info = None


class ArtworkImage:

    def __init__(self, art_id: int, page: int = 0, is_error: bool = False, data: bytes = b""):
        self.art_id = art_id
        self.data = data
        self.is_error = is_error
        if not is_error:
            self.format: str = imghdr.what(None, self.data)
        self.page = page


class ServiceEnum(Enum):
    """
    该名称来源于米忽悠的安卓BBS包名结尾，考虑到大部分重要的功能确实是在移动端实现了
    """
    NULL = None
    HYPERION = 1  # 米忽悠国服
    HOYOLAB = 2  # 米忽悠国际服


class GameItem(BaseObject):
    def __init__(self, item_id: int = 0, name: str = "", item_type: Union[Enum, str, int] = "",
                 value: Union[Enum, str, int, bool, float] = 0):
        self.item_id = item_id
        self.name = name  # 名称
        self.type = item_type  # 类型
        self.value = value  # 数值

    __slots__ = ("name", "type", "value", "item_id")

