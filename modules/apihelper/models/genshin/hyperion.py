import ujson
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO
from typing import Any, List, Optional, Dict

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, PrivateAttr

__all__ = (
    "ArtworkImage",
    "PostInfo",
    "LiveInfo",
    "LiveCode",
    "LiveCodeHoYo",
    "PostTypeEnum",
    "PostRecommend",
    "HoYoPostMultiLang",
)


class ArtworkImage(BaseModel):
    art_id: int
    page: int = 0
    data: bytes = b""
    file_name: Optional[str] = None
    file_extension: Optional[str] = None
    is_error: bool = False

    @property
    def format(self) -> Optional[str]:
        if not self.is_error:
            try:
                with BytesIO(self.data) as stream, Image.open(stream) as im:
                    return im.format
            except UnidentifiedImageError:
                pass
        return None

    @staticmethod
    def gen(*args, **kwargs) -> List["ArtworkImage"]:
        data = [ArtworkImage(*args, **kwargs)]
        if data[0].file_extension and data[0].file_extension in ["gif", "mp4"]:
            return data
        try:
            with BytesIO(data[0].data) as stream, Image.open(stream) as image:
                width, height = image.size
                crop_height = height
                crop_num = 1
                max_height = 10000 - width
                while crop_height > max_height:
                    crop_num += 1
                    crop_height = height / crop_num
                new_data = []
                for i in range(crop_num):
                    slice_image = image.crop((0, crop_height * i, width, crop_height * (i + 1)))
                    bio = BytesIO()
                    slice_image.save(bio, "png")
                    kwargs["data"] = bio.getvalue()
                    kwargs["file_extension"] = "png"
                    new_data.append(ArtworkImage(*args, **kwargs))
                return new_data
        except UnidentifiedImageError:
            return data


class PostInfo(BaseModel):
    _data: dict = PrivateAttr()
    hoyolab: bool
    post_id: int
    user_uid: int
    subject: str
    image_urls: List[str]
    created_at: int
    video_urls: List[str]
    content: str

    def __init__(self, _data: dict, **data: Any):
        super().__init__(**data)
        self._data = _data

    @staticmethod
    def parse_structured_content(data: List[Dict]) -> str:
        content = []
        for item in data:
            if not item or item.get("insert") is None:
                continue
            insert = item["insert"]
            if isinstance(insert, str):
                if attr := item.get("attributes"):
                    if link := attr.get("link"):
                        content.append(f'<p><a href="{link}">{insert}</a></p>')
                        continue
                content.append(f"<p>{insert}</p>")
            elif isinstance(insert, dict):
                if image := insert.get("image"):
                    content.append(f'<img src="{image}" />')
        return "\n".join(content)

    @classmethod
    def paste_data(cls, data: dict, hoyolab: bool = False) -> "PostInfo":
        _data_post = data["post"]
        post = _data_post["post"]
        post_id = post["post_id"]
        subject = post["subject"]
        image_list = []
        image_keys = {"cover_list", "image_list"}
        for key in image_keys:
            image_list.extend(_data_post.get(key, []))
        image_urls = list({image["url"] for image in image_list})
        key1, key2 = ("video", "resolution") if hoyolab else ("vod_list", "resolutions")
        vod_list = _data_post.get(key1, [])
        if not isinstance(vod_list, list):
            vod_list = [vod_list]
        video_urls = [vod[key2][-1]["url"] for vod in vod_list if vod]
        created_at = post["created_at"]
        user = _data_post["user"]  # 用户数据
        user_uid = user["uid"]  # 用户ID
        content = post["content"]
        if hoyolab and ("<" not in content) and (structured_content := post.get("structured_content")):
            content = PostInfo.parse_structured_content(ujson.loads(structured_content))
        if hoyolab and post["view_type"] == 5:
            # video
            content = ujson.loads(content).get("describe", "")
        return PostInfo(
            _data=data,
            hoyolab=hoyolab,
            post_id=post_id,
            user_uid=user_uid,
            subject=subject,
            image_urls=image_urls,
            video_urls=video_urls,
            created_at=created_at,
            content=content,
        )

    def __getitem__(self, item):
        return self._data[item]

    @property
    def type_enum(self) -> "PostTypeEnum":
        return PostTypeEnum.CN if not self.hoyolab else PostTypeEnum.OS

    def get_url(self, short_name: str) -> str:
        if not self.hoyolab:
            return f"https://www.miyoushe.com/{short_name}/article/{self.post_id}"
        return f"https://www.hoyolab.com/article/{self.post_id}"

    def get_fix_url(self, short_name: str) -> str:
        url = self.get_url(short_name)
        return url.replace(".com/", ".pp.ua/")


class LiveInfo(BaseModel):
    act_type: str
    title: str
    live_time: str
    start: datetime
    end: datetime
    remain: int
    now: datetime
    is_end: bool
    code_ver: str


class LiveCode(BaseModel):
    code: str
    to_get_time: datetime

    @property
    def text(self) -> str:
        return self.code if self.code else "XXXXXXXXXXXX"


class LiveCodeHoYo(BaseModel):
    exchange_code: str
    offline_at: datetime

    @property
    def text(self) -> str:
        return self.exchange_code if self.exchange_code else "XXXXXXXXXXXX"

    @staticmethod
    def guess_offline_at() -> datetime:
        return datetime.now().replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)


class PostTypeEnum(str, Enum):
    """社区类型枚举"""

    NULL = "null"
    CN = "cn"
    OS = "os"


class HoYoPostMultiLang(BaseModel):
    lang_subject: dict


class PostRecommend(BaseModel):
    hoyolab: bool = False
    post_id: int

    @staticmethod
    def parse(data: Dict, hoyolab: bool = False):
        _post = data.get("post")
        post_id = _post.get("post_id")
        return PostRecommend(hoyolab=hoyolab, post_id=post_id)
