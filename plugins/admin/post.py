from typing import List, Optional, Tuple, TYPE_CHECKING, Union

from bs4 import BeautifulSoup
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputMediaDocument,
    InputMediaVideo,
)
from telegram.constants import MessageLimit, ParseMode
from telegram.error import BadRequest
from telegram.ext import ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.config import config
from core.plugin import Plugin, conversation, handler
from modules.apihelper.client.components.hyperion import Hyperion
from modules.apihelper.error import APIHelperException
from utils.log import logger

if TYPE_CHECKING:
    from bs4 import Tag
    from telegram import Update, Message
    from telegram.ext import ContextTypes
    from modules.apihelper.models.genshin.hyperion import ArtworkImage


class PostHandlerData:
    def __init__(self):
        self.post_text: str = ""
        self.post_images: Optional[List["ArtworkImage"]] = None
        self.delete_photo: Optional[List[int]] = []
        self.channel_id: int = -1
        self.tags: Optional[List[str]] = []


CHECK_POST, SEND_POST, CHECK_COMMAND, GTE_DELETE_PHOTO = range(10900, 10904)
GET_POST_CHANNEL, GET_TAGS, GET_TEXT = range(10904, 10907)


class Post(Plugin.Conversation):
    """文章推送"""

    MENU_KEYBOARD = ReplyKeyboardMarkup([["推送频道", "添加TAG"], ["编辑文字", "删除图片"], ["退出"]], True, True)

    def __init__(self):
        self.bbs = Hyperion()
        self.last_post_id_list: List[int] = []

    async def initialize(self):
        if config.channels and len(config.channels) > 0:
            logger.success("文章定时推送处理已经开启")
            self.application.job_queue.run_repeating(self.task, 60)

    async def task(self, context: "ContextTypes.DEFAULT_TYPE"):
        temp_post_id_list: List[int] = []

        # 请求推荐POST列表并处理
        try:
            official_recommended_posts = await self.bbs.get_official_recommended_posts(2)
        except APIHelperException as exc:
            logger.error("获取首页推荐信息失败 %s", str(exc))
            return

        for data_list in official_recommended_posts["list"]:
            temp_post_id_list.append(data_list["post_id"])

        # 判断是否为空
        if len(self.last_post_id_list) == 0:
            for temp_list in temp_post_id_list:
                self.last_post_id_list.append(temp_list)
            return

        # 筛选出新推送的文章
        new_post_id_list = set(temp_post_id_list).difference(set(self.last_post_id_list))

        if len(new_post_id_list) == 0:
            return

        self.last_post_id_list = temp_post_id_list

        for post_id in new_post_id_list:
            try:
                post_info = await self.bbs.get_post_info(2, post_id)
            except APIHelperException as exc:
                logger.error("获取文章信息失败 %s", str(exc))
                text = f"获取 post_id[{post_id}] 文章信息失败 {str(exc)}"
                for user in config.admins:
                    try:
                        await context.bot.send_message(user.user_id, text)
                    except BadRequest as _exc:
                        logger.error("发送消息失败 %s", _exc.message)
                return
            buttons = [
                [
                    InlineKeyboardButton("确认", callback_data=f"post_admin|confirm|{post_info.post_id}"),
                    InlineKeyboardButton("取消", callback_data=f"post_admin|cancel|{post_info.post_id}"),
                ]
            ]
            url = f"https://www.miyoushe.com/ys/article/{post_info.post_id}"
            text = f"发现官网推荐文章 <a href='{url}'>{post_info.subject}</a>\n是否开始处理"
            try:
                await context.bot.send_message(
                    config.owner, text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
                )
            except BadRequest as exc:
                logger.error("发送消息失败 %s", exc.message)

    @staticmethod
    def parse_post_text(soup: BeautifulSoup, post_subject: str) -> str:
        def parse_tag(_tag: "Tag") -> str:
            if _tag.name == "a" and _tag.get("href"):
                return f"[{escape_markdown(_tag.get_text(), version=2)}]({_tag.get('href')})"
            return escape_markdown(_tag.get_text(), version=2)

        post_p = soup.find_all("p")
        post_text = f"*{escape_markdown(post_subject, version=2)}*\n\n"
        start = True
        for p in post_p:
            t = p.get_text()
            if not t and start:
                continue
            start = False
            for tag in p.contents:
                post_text += parse_tag(tag)
            post_text += "\n"
        return post_text

    @staticmethod
    def input_media(
        media: "ArtworkImage", *args, **kwargs
    ) -> Union[None, InputMediaDocument, InputMediaPhoto, InputMediaVideo]:
        file_type = media.format
        if file_type in {"jpg", "jpeg", "png", "webp"}:
            return InputMediaPhoto(media.data, *args, **kwargs)
        if file_type in {"gif", "mp4", "mov", "avi", "mkv", "webm", "flv"}:
            return InputMediaVideo(media.data, *args, **kwargs)
        return InputMediaDocument(media.data, *args, **kwargs)

    @conversation.entry_point
    @handler.callback_query(pattern=r"^post_admin\|", block=False)
    async def callback_query_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        post_handler_data = context.chat_data.get("post_handler_data")
        if post_handler_data is None:
            post_handler_data = PostHandlerData()
            context.chat_data["post_handler_data"] = post_handler_data
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message
        logger.info("用户 %s[%s] POST命令请求", user.full_name, user.id)

        async def get_post_admin_callback(callback_query_data: str) -> Tuple[str, int]:
            _data = callback_query_data.split("|")
            _result = _data[1]
            _post_id = int(_data[2])
            logger.debug("callback_query_data函数返回 result[%s] post_id[%s]", _result, _post_id)
            return _result, _post_id

        result, post_id = await get_post_admin_callback(callback_query.data)

        if result == "cancel":
            await message.reply_text("操作已经取消")
            await message.delete()
        elif result == "confirm":
            reply_text = await message.reply_text("正在处理")
            status = await self.send_post_info(post_handler_data, message, post_id)
            await reply_text.delete()
            return status

        await message.reply_text("非法参数")
        return ConversationHandler.END

    @conversation.entry_point
    @handler.command(command="post", filters=filters.ChatType.PRIVATE, block=False, admin=True)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] POST命令请求", user.full_name, user.id)
        post_handler_data = context.chat_data.get("post_handler_data")
        if post_handler_data is None:
            post_handler_data = PostHandlerData()
            context.chat_data["post_handler_data"] = post_handler_data
        text = f"✿✿ヽ（°▽°）ノ✿ 你好！ {user.username} ，\n" "只需复制URL回复即可 \n" "退出投稿只需回复退出"
        reply_keyboard = [["退出"]]
        await message.reply_text(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, True, True))
        return CHECK_POST

    @conversation.state(state=CHECK_POST)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def check_post(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出投稿", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

        post_id = self.bbs.extract_post_id(update.message.text)
        if post_id == -1:
            await message.reply_text("获取作品ID错误，请检查连接是否合法", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        return await self.send_post_info(post_handler_data, message, post_id)

    async def send_post_info(self, post_handler_data: PostHandlerData, message: "Message", post_id: int) -> int:
        post_info = await self.bbs.get_post_info(2, post_id)
        post_images = await self.bbs.get_images_by_post_id(2, post_id)
        post_data = post_info["post"]["post"]
        post_subject = post_data["subject"]
        post_soup = BeautifulSoup(post_data["content"], features="html.parser")
        post_text = self.parse_post_text(post_soup, post_subject)
        post_text += f"[source](https://www.miyoushe.com/ys/article/{post_id})"
        if len(post_text) >= MessageLimit.CAPTION_LENGTH:
            post_text = post_text[: MessageLimit.CAPTION_LENGTH]
            await message.reply_text(f"警告！图片字符描述已经超过 {MessageLimit.CAPTION_LENGTH} 个字，已经切割")
        try:
            if len(post_images) > 1:
                media = [self.input_media(img_info) for img_info in post_images if img_info.format]
                media[0] = self.input_media(media=post_images[0], caption=post_text, parse_mode=ParseMode.MARKDOWN_V2)
                if len(media) > 10:
                    media = media[:10]
                    await message.reply_text("获取到的图片已经超过10张，为了保证发送成功，已经删除一部分图片")
                await message.reply_media_group(media)
            elif len(post_images) == 1:
                image = post_images[0]
                await message.reply_photo(image.data, caption=post_text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await message.reply_text(post_text, reply_markup=ReplyKeyboardRemove())
                return ConversationHandler.END
        except BadRequest as exc:
            await message.reply_text(f"发送图片时发生错误 {exc.message}", reply_markup=ReplyKeyboardRemove())
            logger.error("Post模块发送图片时发生错误", exc_info=exc)
            return ConversationHandler.END
        except TypeError as exc:
            await message.reply_text("发送图片时发生错误，错误信息已经写到日记", reply_markup=ReplyKeyboardRemove())
            logger.error("Post模块发送图片时发生错误", exc_info=exc)

            return ConversationHandler.END
        post_handler_data.post_text = post_text
        post_handler_data.post_images = post_images
        post_handler_data.delete_photo = []
        post_handler_data.tags = []
        post_handler_data.channel_id = -1
        await message.reply_text("请选择你的操作", reply_markup=self.MENU_KEYBOARD)
        return CHECK_COMMAND

    @conversation.state(state=CHECK_COMMAND)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def check_command(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "推送频道":
            return await self.get_channel(update, context)
        if message.text == "添加TAG":
            return await self.add_tags(update, context)
        if message.text == "编辑文字":
            return await self.edit_text(update, context)
        if message.text == "删除图片":
            return await self.delete_photo(update, context)
        return ConversationHandler.END

    @staticmethod
    async def delete_photo(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        photo_len = len(post_handler_data.post_images)
        message = update.effective_message
        await message.reply_text("请回复你要删除的图片的序列，从1开始，如果删除多张图片回复的序列请以空格作为分隔符，" f"当前一共有 {photo_len} 张图片")
        return GTE_DELETE_PHOTO

    @conversation.state(state=GTE_DELETE_PHOTO)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def get_delete_photo(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        photo_len = len(post_handler_data.post_images)
        message = update.effective_message
        args = message.text.split(" ")
        index: List[int] = []
        try:
            for temp in args:
                if int(temp) > photo_len:
                    raise ValueError
                index.append(int(temp))
        except ValueError:
            await message.reply_text("数据不合法，请重新操作")
            return GTE_DELETE_PHOTO
        post_handler_data.delete_photo = index
        await message.reply_text("删除成功")
        await message.reply_text("请选择你的操作", reply_markup=self.MENU_KEYBOARD)
        return CHECK_COMMAND

    async def get_channel(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        reply_keyboard = []
        try:
            for channel_id in config.channels:
                chat = await self.get_chat(chat_id=channel_id)
                reply_keyboard.append([f"{chat.username}"])
        except KeyError as error:
            logger.error("从配置文件获取频道信息发生错误，退出任务", exc_info=error)
            await message.reply_text("从配置文件获取频道信息发生错误，退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("请选择你要推送的频道", reply_markup=ReplyKeyboardMarkup(reply_keyboard, True, True))
        return GET_POST_CHANNEL

    @conversation.state(state=GET_POST_CHANNEL)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def get_post_channel(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        channel_id = -1
        try:
            for channel_chat_id in config.channels:
                chat = await self.get_chat(chat_id=channel_chat_id)
                if message.text == chat.username:
                    channel_id = channel_chat_id
        except KeyError as exc:
            logger.error("从配置文件获取频道信息发生错误，退出任务", exc_info=exc)
            logger.exception(exc)
            await message.reply_text("从配置文件获取频道信息发生错误，退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if channel_id == -1:
            await message.reply_text("获取频道信息失败，请检查你输入的内容是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        post_handler_data.channel_id = channel_id
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("请核对你修改的信息", reply_markup=ReplyKeyboardMarkup(reply_keyboard, True, True))
        return SEND_POST

    @staticmethod
    async def add_tags(update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        await message.reply_text("请回复添加的tag名称，如果要添加多个tag请以空格作为分隔符，不用添加 # 作为开头，推送时程序会自动添加")
        return GET_TAGS

    @conversation.state(state=GET_TAGS)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def get_tags(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        args = message.text.split(" ")
        post_handler_data.tags = args
        await message.reply_text("添加成功")
        await message.reply_text("请选择你的操作", reply_markup=self.MENU_KEYBOARD)
        return CHECK_COMMAND

    @staticmethod
    async def edit_text(update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        await message.reply_text("请回复替换的文本")
        return GET_TEXT

    @conversation.state(state=GET_TEXT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def get_edit_text(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        post_handler_data.post_text = message.text_markdown_v2
        await message.reply_text("替换成功")
        await message.reply_text("请选择你的操作", reply_markup=self.MENU_KEYBOARD)
        return CHECK_COMMAND

    @conversation.state(state=SEND_POST)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def send_post(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text(text="退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("正在推送", reply_markup=ReplyKeyboardRemove())
        channel_id = post_handler_data.channel_id
        channel_name = None
        try:
            for channel_info in config.channels:
                if post_handler_data.channel_id == channel_info:
                    chat = await self.get_chat(chat_id=channel_id)
                    channel_name = chat.username
        except KeyError as exc:
            logger.error("从配置文件获取频道信息发生错误，退出任务")
            logger.exception(exc)
            await message.reply_text("从配置文件获取频道信息发生错误，退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        post_text = post_handler_data.post_text
        post_images = []
        for index, _ in enumerate(post_handler_data.post_images):
            if index + 1 not in post_handler_data.delete_photo:
                post_images.append(post_handler_data.post_images[index])
        post_text += f" @{escape_markdown(channel_name, version=2)}"
        for tag in post_handler_data.tags:
            post_text += f" \\#{tag}"
        try:
            if len(post_images) > 1:
                media = [self.input_media(img_info) for img_info in post_images if img_info.format]
                media[0] = self.input_media(media=post_images[0], caption=post_text, parse_mode=ParseMode.MARKDOWN_V2)
                await context.bot.send_media_group(channel_id, media=media)
            elif len(post_images) == 1:
                image = post_images[0]
                await context.bot.send_photo(
                    channel_id, photo=image.data, caption=post_text, parse_mode=ParseMode.MARKDOWN_V2
                )
            elif not post_images:
                await context.bot.send_message(channel_id, post_text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await message.reply_text("图片获取错误", reply_markup=ReplyKeyboardRemove())  # excuse?
                return ConversationHandler.END
        except BadRequest as exc:
            await message.reply_text(f"发送图片时发生错误 {exc.message}", reply_markup=ReplyKeyboardRemove())
            logger.error("Post模块发送图片时发生错误", exc_info=exc)
            return ConversationHandler.END
        except TypeError as exc:
            await message.reply_text("发送图片时发生错误，错误信息已经写到日记", reply_markup=ReplyKeyboardRemove())
            logger.error("Post模块发送图片时发生错误", exc_info=exc)
        await message.reply_text("推送成功", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
