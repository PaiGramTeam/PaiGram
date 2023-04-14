from io import BytesIO
from typing import Any, List, Optional

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, PrivateAttr

__all__ = ("ArtworkImage", "PostInfo")


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


class PostInfo(BaseModel):
    _data: dict = PrivateAttr()
    post_id: int
    user_uid: int
    subject: str
    image_urls: List[str]
    created_at: int
    video_urls: List[str]

    def __init__(self, _data: dict, **data: Any):
        super().__init__(**data)
        self._data = _data

    @classmethod
    def paste_data(cls, data: dict) -> "PostInfo":
        _data_post = data["post"]
        post = _data_post["post"]
        post_id = post["post_id"]
        subject = post["subject"]
        image_list = _data_post["image_list"]
        image_urls = [image["url"] for image in image_list]
        vod_list = _data_post["vod_list"]
        video_urls = [vod["resolutions"][-1]["url"] for vod in vod_list]
        created_at = post["created_at"]
        user = _data_post["user"]  # 用户数据
        user_uid = user["uid"]  # 用户ID
        return PostInfo(
            _data=data,
            post_id=post_id,
            user_uid=user_uid,
            subject=subject,
            image_urls=image_urls,
            video_urls=video_urls,
            created_at=created_at,
        )

    def __getitem__(self, item):
        return self._data[item]
