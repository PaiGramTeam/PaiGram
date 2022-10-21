from enum import Enum
from typing import Optional, Union, List

from playwright.async_api import ViewportSize
from pydantic import BaseModel
from telegram import Message, InputMediaPhoto

from core.template import HtmlToFileIdCache


class InputRenderData(BaseModel):
    template_name: str
    template_data: dict
    viewport: ViewportSize = None
    full_page: bool = True
    evaluate: Optional[str] = None
    query_selector: str = None


class FileType(Enum):
    PHOTO = 1
    DOCUMENT = 2


class RenderResult:
    """渲染结果"""

    def __init__(self, html: str, photo: Union[bytes, str], file_type: FileType, cache: HtmlToFileIdCache):
        """
        `html`: str 渲染生成的 html
        `photo`: Union[bytes, str] 渲染生成的图片。bytes 表示是图片，str 则为 file_id
        """
        self.html = html
        self.photo = photo
        self.file_type = file_type
        self._cache = cache

    async def reply_photo(self, message: Message, *args, **kwargs):
        """是 `message.reply_photo` 的封装，上传成功后，缓存 telegram 返回的 file_id，方便重复使用"""
        reply = await message.reply_photo(self.photo, *args, **kwargs)

        await self.cache_file_id(reply)

        return reply

    async def cache_file_id(self, reply: Message):
        """缓存 telegram 返回的 file_id"""
        if self.is_file_id():
            return

        photo = reply.photo[0]
        file_id = photo.file_id
        await self._cache.set_data(self.html, self.file_type, file_id)

    def is_file_id(self) -> bool:
        return isinstance(self.photo, str)


class RenderGroupResult:
    def __init__(self, results: List[RenderResult], cache: HtmlToFileIdCache):
        self.results = results
        self._cache = cache

    async def reply_media_group(self, message: Message, *args, **kwargs):
        reply = await message.reply_media_group(
            media=[InputMediaPhoto(result.photo) for result in self.results], *args, **kwargs
        )

        for index, value in enumerate(reply):
            result = self.results[index]
            await result.cache_file_id(value)
