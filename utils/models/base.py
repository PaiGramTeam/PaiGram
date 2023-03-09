import os
from enum import Enum
from typing import Optional

from PIL import Image, UnidentifiedImageError
from pydantic import BaseSettings

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib


class Stat:
    def __init__(
        self, view_num: int = 0, reply_num: int = 0, like_num: int = 0, bookmark_num: int = 0, forward_num: int = 0
    ):
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
        self.page = page

    @property
    def format(self):
        try:
            with Image.open(self.data) as im:
                return im.format
        except UnidentifiedImageError:
            return None


class RegionEnum(Enum):
    """注册服务器的列举型别

    HYPERION名称来源于米忽悠BBS的安卓端包名结尾

    查了一下确实有点意思 考虑到大部分重要的功能确实是在移动端实现了

    干脆用这个还好听 ）"""

    NULL = None
    HYPERION = 1  # 米忽悠国服 hyperion
    HOYOLAB = 2  # 米忽悠国际服 hoyolab


class ModuleInfo:
    def __init__(
        self, file_name: Optional[str] = None, plugin_name: Optional[str] = None, relative_path: Optional[str] = None
    ):
        self.relative_path = relative_path
        self.module_name = plugin_name
        self.file_name = file_name
        if file_name is None:
            if relative_path is None:
                raise ValueError("file_name 和 relative_path 都不能为空")
            self.file_name = os.path.basename(relative_path)
        if plugin_name is None:
            self.module_name, _ = os.path.splitext(self.file_name)

    @property
    def package_path(self) -> str:
        if self.relative_path is None:
            return ""
        if os.path.isdir(self.relative_path):
            return self.relative_path.replace("/", ".")
        root, _ = os.path.splitext(self.relative_path)
        return root.replace("/", ".")

    def __str__(self):
        return self.module_name


class Settings(BaseSettings):
    def __new__(cls, *args, **kwargs):
        cls.update_forward_refs()
        return super(Settings, cls).__new__(cls)  # pylint: disable=E1120

    class Config(BaseSettings.Config):
        case_sensitive = False
        json_loads = jsonlib.loads
        json_dumps = jsonlib.dumps
