import imghdr
from typing import List, Any, Union

from pydantic import BaseModel, PrivateAttr

__all__ = ("ArtworkImage", "PostInfo")

from telegram import InputMediaPhoto, InputMediaVideo, InputMediaDocument


class ArtworkImage(BaseModel):
    art_id: int
    page: int = 0
    data: bytes = b""
    is_error: bool = False

    @property
    def format(self) -> str:
        return "" if self.is_error else imghdr.what(None, self.data)

    def input_media(self, *args, **kwargs) -> Union[None, InputMediaDocument, InputMediaPhoto, InputMediaVideo]:
        file_type = self.format
        if not file_type:
            return None
        elif file_type in {"jpeg", "png", "webp"}:
            return InputMediaPhoto(self.data, *args, **kwargs)
        elif file_type in {"gif", "mp4", "mov", "avi", "mkv", "webm", "flv"}:
            return InputMediaVideo(self.data, *args, **kwargs)
        else:
            return InputMediaDocument(self.data, *args, **kwargs)


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
