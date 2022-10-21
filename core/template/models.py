from enum import Enum
from typing import Optional, Union, List

from telegram import Message, InputMediaPhoto

from core.template.cache import HtmlToFileIdCache
from core.template.error import ErrorFileType


class FileType(Enum):
    PHOTO = 1
    DOCUMENT = 2


class RenderResult:
    """渲染结果"""

    def __init__(
        self,
        html: str,
        photo: Union[bytes, str],
        file_type: FileType,
        cache: HtmlToFileIdCache,
        ttl: int = 24 * 60 * 60,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        filename: Optional[str] = None,
    ):
        """
        `html`: str 渲染生成的 html
        `photo`: Union[bytes, str] 渲染生成的图片。bytes 表示是图片，str 则为 file_id
        """
        self.caption = caption
        self.parse_mode = parse_mode
        self.filename = filename
        self.html = html
        self.photo = photo
        self.file_type = file_type
        self._cache = cache
        self.ttl = ttl

    async def reply_photo(self, message: Message, *args, **kwargs):
        """是 `message.reply_photo` 的封装，上传成功后，缓存 telegram 返回的 file_id，方便重复使用"""
        if self.file_type != FileType.PHOTO:
            raise ErrorFileType

        reply = await message.reply_photo(photo=self.photo, *args, **kwargs)

        await self.cache_file_id(reply, self.ttl)

        return reply

    async def reply_document(self, message: Message, *args, **kwargs):
        """是 `message.reply_document` 的封装，上传成功后，缓存 telegram 返回的 file_id，方便重复使用"""
        if self.file_type != FileType.DOCUMENT:
            raise ErrorFileType

        reply = await message.reply_document(document=self.photo, *args, **kwargs)

        await self.cache_file_id(reply, self.ttl)

        return reply

    async def edit_media(self, message: Message, *args, **kwargs):
        """是 `message.edit_media` 的封装，上传成功后，缓存 telegram 返回的 file_id，方便重复使用"""
        if self.file_type != FileType.PHOTO:
            raise ErrorFileType

        media = InputMediaPhoto(
            media=self.photo, caption=self.caption, parse_mode=self.parse_mode, filename=self.filename
        )

        edit_media = await message.edit_media(media, *args, **kwargs)

        await self.cache_file_id(edit_media, self.ttl)

        return edit_media

    async def cache_file_id(self, reply: Message, ttl: int = 24 * 60 * 60):
        """缓存 telegram 返回的 file_id"""
        if self.is_file_id():
            return

        photo = reply.photo[0]
        file_id = photo.file_id
        await self._cache.set_data(self.html, self.file_type.name, file_id, ttl)

    def is_file_id(self) -> bool:
        return isinstance(self.photo, str)


class RenderGroupResult:
    def __init__(self, results: List[RenderResult]):
        self.results = results

    async def reply_media_group(self, message: Message, *args, **kwargs):
        """是 `message.reply_media_group` 的封装，上传成功后，缓存 telegram 返回的 file_id，方便重复使用"""
        for result in self.results:
            if result.file_type != FileType.PHOTO:
                raise ErrorFileType

        reply = await message.reply_media_group(
            media=[
                InputMediaPhoto(
                    media=result.photo, caption=result.caption, parse_mode=result.parse_mode, filename=result.filename
                )
                for result in self.results
            ],
            *args,
            **kwargs,
        )

        for index, value in enumerate(reply):
            result = self.results[index]
            await result.cache_file_id(value, result.ttl)
