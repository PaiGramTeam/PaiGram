import imghdr
from typing import Any, List

from pydantic import BaseModel, PrivateAttr

__all__ = ("ArtworkImage", "PostInfo")


class ArtworkImage(BaseModel):
    art_id: int
    page: int = 0
    data: bytes = b""
    is_error: bool = False

    @property
    def format(self) -> str:
        if self.is_error:
            return ""
        else:
            imghdr.what(None, self.data)


class PostInfo(BaseModel):
    _data: dict = PrivateAttr()
    post_id: int
    user_uid: int
    subject: str
    image_urls: List[str]
    created_at: int

    def __init__(self, _data: dict, **data: Any):
        super().__init__(**data)
        self._data = _data

    @classmethod
    def paste_data(cls, data: dict) -> "PostInfo":
        image_urls = []
        _data_post = data["post"]
        post = _data_post["post"]
        post_id = post["post_id"]
        subject = post["subject"]
        image_list = _data_post["image_list"]
        for image in image_list:
            image_urls.append(image["url"])
        created_at = post["created_at"]
        user = _data_post["user"]  # 用户数据
        user_uid = user["uid"]  # 用户ID
        return PostInfo(
            _data=data,
            post_id=post_id,
            user_uid=user_uid,
            subject=subject,
            image_urls=image_urls,
            created_at=created_at,
        )

    def __getitem__(self, item):
        return self._data[item]
