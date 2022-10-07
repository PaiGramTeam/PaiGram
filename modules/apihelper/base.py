import imghdr
from typing import List

from pydantic import BaseModel


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
    _data: dict
    post_id: int
    user_uid: int
    image_urls: List[str] = []
    created_at: int

    @classmethod
    def paste_data(cls, data: dict):
        image_url_list = []
        _data_post = data["post"]
        post = _data_post["post"]
        post_id = post["post_id"]
        image_list = _data_post["image_list"]
        for image in image_list:
            image_url_list.append(image["url"])
        created_at = post["created_at"]
        user = _data_post["user"]  # 用户数据
        user_uid = user["uid"]  # 用户ID
        return cls(_data=data, post_id=post_id, user_uid=user_uid, image_urls=image_url_list, created_at=created_at)

    def __dict__(self):
        return self._data
