from typing import Optional, List

from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.constants import ParseMode, MessageLimit
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.baseplugin import BasePlugin
from core.bot import bot
from core.plugin import Plugin, conversation, handler
from modules.apihelper.base import ArtworkImage
from modules.apihelper.hyperion import Hyperion
from utils.decorators.admins import bot_admins_rights_check
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class PostHandlerData:

    def __init__(self):
        self.post_text: str = ""
        self.post_images: Optional[List[ArtworkImage]] = None
        self.delete_photo: Optional[List[int]] = []
        self.channel_id: int = -1
        self.tags: Optional[List[str]] = []


CHECK_POST, SEND_POST, CHECK_COMMAND, GTE_DELETE_PHOTO = range(10900, 10904)
GET_POST_CHANNEL, GET_TAGS, GET_TEXT = range(10904, 10907)


class Post(Plugin.Conversation, BasePlugin):
    """文章推送"""

    MENU_KEYBOARD = ReplyKeyboardMarkup([["推送频道", "添加TAG"], ["编辑文字", "删除图片"], ["退出"]], True, True)

    def __init__(self):
        self.bbs = Hyperion()

    @conversation.entry_point
    @handler.command(command='post', filters=filters.ChatType.PRIVATE, block=True)
    @restricts()
    @bot_admins_rights_check
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] POST命令请求")
        post_handler_data = context.chat_data.get("post_handler_data")
        if post_handler_data is None:
            post_handler_data = PostHandlerData()
            context.chat_data["post_handler_data"] = post_handler_data
        text = f"✿✿ヽ（°▽°）ノ✿ 你好！ {user.username} ，\n" \
               "只需复制URL回复即可 \n" \
               "退出投稿只需回复退出"
        reply_keyboard = [['退出']]
        await message.reply_text(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, True, True))
        return self.CHECK_POST

    @conversation.state(state=CHECK_POST)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_post(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出投稿", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

        post_id = self.bbs.extract_post_id(update.message.text)
        if post_id == -1:
            await message.reply_text("获取作品ID错误，请检查连接是否合法", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        post_full_info = await self.bbs.get_post_full_info(2, post_id)
        post_images = await self.bbs.get_images_by_post_id(2, post_id)
        post_data = post_full_info.data["post"]["post"]
        post_subject = post_data['subject']
        post_soup = BeautifulSoup(post_data["content"], features="html.parser")
        post_p = post_soup.find_all('p')
        post_text = f"*{escape_markdown(post_subject, version=2)}*\n" \
                    f"\n"
        for p in post_p:
            post_text += f"{escape_markdown(p.get_text(), version=2)}\n"
        post_text += f"[source](https://bbs.mihoyo.com/ys/article/{post_id})"
        if len(post_text) >= MessageLimit.CAPTION_LENGTH:
            await message.reply_markdown_v2(post_text)
            post_text = post_text[0:MessageLimit.CAPTION_LENGTH]
            await message.reply_text(f"警告！图片字符描述已经超过 {MessageLimit.CAPTION_LENGTH} 个字，已经切割并发送原文本")
        try:
            if len(post_images) > 1:
                media = [InputMediaPhoto(img_info.data) for img_info in post_images]
                media[0] = InputMediaPhoto(post_images[0].data, caption=post_text, parse_mode=ParseMode.MARKDOWN_V2)
                await message.reply_media_group(media)
            elif len(post_images) == 1:
                image = post_images[0]
                await message.reply_photo(image.data, caption=post_text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await message.reply_text("图片获取错误", reply_markup=ReplyKeyboardRemove())  # excuse?
                return ConversationHandler.END
        except (BadRequest, TypeError) as exc:
            await message.reply_text("发送图片时发生错误，错误信息已经写到日记", reply_markup=ReplyKeyboardRemove())
            logger.error("Post模块发送图片时发生错误")
            logger.exception(exc)
            return ConversationHandler.END
        post_handler_data.post_text = post_text
        post_handler_data.post_images = post_images
        post_handler_data.delete_photo = []
        post_handler_data.tags = []
        post_handler_data.channel_id = -1
        await message.reply_text("请选择你的操作", reply_markup=self.MENU_KEYBOARD)
        return self.CHECK_COMMAND

    @conversation.state(state=CHECK_COMMAND)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_command(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif message.text == "推送频道":
            return await self.get_channel(update, context)
        elif message.text == "添加TAG":
            return await self.add_tags(update, context)
        elif message.text == "编辑文字":
            return await self.edit_text(update, context)
        elif message.text == "删除图片":
            return await self.delete_photo(update, context)
        return ConversationHandler.END

    async def delete_photo(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        photo_len = len(post_handler_data.post_images)
        message = update.message
        await message.reply_text("请回复你要删除的图片的序列，从1开始，如果删除多张图片回复的序列请以空格作为分隔符，"
                                 f"当前一共有 {photo_len} 张图片")
        return self.GTE_DELETE_PHOTO

    @conversation.state(state=GTE_DELETE_PHOTO)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def get_delete_photo(self, update: Update, context: CallbackContext) -> int:
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
            return self.GTE_DELETE_PHOTO
        post_handler_data.delete_photo = index
        await message.reply_text("删除成功")
        await message.reply_text("请选择你的操作", reply_markup=self.MENU_KEYBOARD)
        return self.CHECK_COMMAND

    async def get_channel(self, update: Update, _: CallbackContext) -> int:
        message = update.effective_message
        reply_keyboard = []
        try:
            for channel_info in bot.config.channels:
                name = channel_info["name"]
                reply_keyboard.append([f"{name}"])
        except KeyError as error:
            logger.error("从配置文件获取频道信息发生错误，退出任务", error)
            await message.reply_text("从配置文件获取频道信息发生错误，退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("请选择你要推送的频道",
                                 reply_markup=ReplyKeyboardMarkup(reply_keyboard, True, True))
        return self.GET_POST_CHANNEL

    @conversation.state(state=GET_POST_CHANNEL)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def get_post_channel(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        channel_id = -1
        try:
            for channel_info in bot.config.channels:
                if message.text == channel_info["name"]:
                    channel_id = channel_info["chat_id"]
        except KeyError as exc:
            logger.error("从配置文件获取频道信息发生错误，退出任务", exc)
            logger.exception(exc)
            await message.reply_text("从配置文件获取频道信息发生错误，退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if channel_id == -1:
            await message.reply_text("获取频道信息失败，请检查你输入的内容是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        post_handler_data.channel_id = channel_id
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("请核对你修改的信息",
                                 reply_markup=ReplyKeyboardMarkup(reply_keyboard, True, True))
        return self.SEND_POST

    async def add_tags(self, update: Update, _: CallbackContext) -> int:
        message = update.effective_message
        await message.reply_text("请回复添加的tag名称，如果要添加多个tag请以空格作为分隔符，不用添加 # 作为开头，推送时程序会自动添加")
        return self.GET_TAGS

    @conversation.state(state=GET_TAGS)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def get_tags(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        args = message.text.split(" ")
        post_handler_data.tags = args
        await message.reply_text("添加成功")
        await message.reply_text("请选择你的操作", reply_markup=self.MENU_KEYBOARD)
        return self.CHECK_COMMAND

    async def edit_text(self, update: Update, _: CallbackContext) -> int:
        message = update.effective_message
        await message.reply_text("请回复替换的文本")
        return self.GET_TEXT

    @conversation.state(state=GET_TEXT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def get_edit_text(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        post_handler_data.post_text = message.text_markdown_v2
        await message.reply_text("替换成功")
        await message.reply_text("请选择你的操作", reply_markup=self.MENU_KEYBOARD)
        return self.CHECK_COMMAND

    @staticmethod
    @error_callable
    async def send_post(update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text(text="退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("正在推送", reply_markup=ReplyKeyboardRemove())
        channel_id = post_handler_data.channel_id
        channel_name = None
        try:
            for channel_info in bot.config.channels:
                if post_handler_data.channel_id == channel_info["chat_id"]:
                    channel_name = channel_info["name"]
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
        post_text += f" @{channel_name}"
        for tag in post_handler_data.tags:
            post_text += f" \\#{tag}"
        try:
            if len(post_images) > 1:
                media = [InputMediaPhoto(img_info.data) for img_info in post_images]
                media[0] = InputMediaPhoto(post_images[0].data, caption=post_text, parse_mode=ParseMode.MARKDOWN_V2)
                await context.bot.send_media_group(channel_id, media=media)
            elif len(post_images) == 1:
                image = post_images[0]
                await context.bot.send_photo(channel_id, photo=image.data, caption=post_text,
                                             parse_mode=ParseMode.MARKDOWN_V2)
            elif len(post_images) == 0:
                await context.bot.send_message(channel_id, post_text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await message.reply_text("图片获取错误", reply_markup=ReplyKeyboardRemove())  # excuse?
                return ConversationHandler.END
        except (BadRequest, TypeError) as exc:
            await message.reply_text("发送图片时发生错误，错误信息已经写到日记", reply_markup=ReplyKeyboardRemove())
            logger.error("Post模块发送图片时发生错误")
            logger.exception(exc)
            return ConversationHandler.END
        await message.reply_text("推送成功", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
