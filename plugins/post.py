from typing import Optional, List

from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, MessageHandler, filters
from telegram.helpers import escape_markdown

from config import config
from logger import Log
from model.apihelper import Hyperion, ArtworkImage
from plugins.base import BasePlugins
from service import BaseService


class PostHandlerData:
    """
    文章推送
    """
    def __init__(self):
        self.post_text: str = ""
        self.post_images: Optional[List[ArtworkImage]] = None
        self.delete_photo: Optional[List[int]] = []
        self.channel_id: int = -1
        self.tags: Optional[List[str]] = []


class Post(BasePlugins):
    CHECK_POST, SEND_POST, CHECK_COMMAND, GTE_DELETE_PHOTO = range(10900, 10904)
    GET_POST_CHANNEL, GET_TAGS, GET_TEXT = range(10904, 10907)

    def __init__(self, service: BaseService):
        super().__init__(service)
        self.bbs = Hyperion()

    @staticmethod
    def create_conversation_handler(service: BaseService):
        _post = Post(service)
        post_handler = ConversationHandler(
            entry_points=[CommandHandler('post', _post.command_start, block=True)],
            states={
                _post.CHECK_POST: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.check_post, block=True)],
                _post.SEND_POST: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.send_post, block=True)],
                _post.CHECK_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.check_command, block=True)],
                _post.GTE_DELETE_PHOTO: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, _post.get_delete_photo, block=True)],
                _post.GET_POST_CHANNEL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, _post.get_post_channel, block=True)],
                _post.GET_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.get_tags, block=True)],
                _post.GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.get_edit_text, block=True)]
            },
            fallbacks=[CommandHandler('cancel', _post.cancel, block=True)]
        )
        return post_handler

    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.message
        Log.info(f"用户 {user.full_name}[{user.id}] POST命令请求")
        admin_list = await self.service.admin.get_admin_list()
        if user.id not in admin_list:
            await message.reply_text("你不是BOT管理员，不能使用此命令！")
            return ConversationHandler.END
        post_handler_data = context.chat_data.get("post_handler_data")
        if post_handler_data is None:
            post_handler_data = PostHandlerData()
            context.chat_data["post_handler_data"] = post_handler_data
        text = "✿✿ヽ（°▽°）ノ✿ 你好！ %s ，\n" \
               "只需复制URL回复即可 \n" \
               "退出投稿只需回复退出" % (user["username"])
        reply_keyboard = [['退出']]
        await message.reply_text(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.CHECK_POST

    async def check_post(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.message
        if update.message.text == "退出":
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
        except (BadRequest, TypeError) as error:
            await message.reply_text("图片获取错误，错误信息已经写到日记", reply_markup=ReplyKeyboardRemove())
            Log.error("Post模块图片获取错误", error)
            return ConversationHandler.END
        post_handler_data.post_text = post_text
        post_handler_data.post_images = post_images
        post_handler_data.delete_photo = []
        post_handler_data.tags = []
        post_handler_data.channel_id = -1
        text = "请选择你的操作"
        reply_keyboard = [["推送频道", "添加TAG"], ["编辑文字", "删除图片"], ["退出"]]
        await message.reply_text(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.CHECK_COMMAND

    async def check_command(self, update: Update, context: CallbackContext) -> int:
        message = update.message
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

    async def get_delete_photo(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        photo_len = len(post_handler_data.post_images)
        message = update.message
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
        text = "请选择你的操作"
        reply_keyboard = [["推送频道", "添加TAG"], ["编辑文字", "删除图片"], ["退出"]]
        await message.reply_text(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.CHECK_COMMAND

    async def get_channel(self, update: Update, _: CallbackContext) -> int:
        message = update.message
        reply_keyboard = []
        try:
            for channel_info in config.TELEGRAM["channel"]["POST"]:
                name = channel_info["name"]
                reply_keyboard.append([f"{name}"])
        except KeyError as error:
            Log.error("从配置文件获取频道信息发生错误，退出任务", error)
            await message.reply_text("从配置文件获取频道信息发生错误，退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("请选择你要推送的频道",
                                 reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.GET_POST_CHANNEL

    async def get_post_channel(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.message
        channel_id = -1
        try:
            for channel_info in config.TELEGRAM["channel"]["POST"]:
                if message.text == channel_info["name"]:
                    channel_id = channel_info["chat_id"]
        except KeyError as error:
            Log.error("从配置文件获取频道信息发生错误，退出任务", error)
            await message.reply_text("从配置文件获取频道信息发生错误，退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if channel_id == -1:
            await message.reply_text("获取频道信息失败，请检查你输入的内容是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        post_handler_data.channel_id = channel_id
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("请核对你修改的信息",
                                 reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.SEND_POST

    async def add_tags(self, update: Update, _: CallbackContext) -> int:
        message = update.message
        await message.reply_text("请回复添加的tag名称，如果要添加多个tag请以空格作为分隔符")
        return self.GET_TAGS

    async def get_tags(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.message
        args = message.text.split(" ")
        post_handler_data.tags = args
        await message.reply_text("添加成功")
        text = "请选择你的操作"
        reply_keyboard = [["推送频道", "添加TAG"], ["编辑文字", "删除图片"], ["退出"]]
        await message.reply_text(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.CHECK_COMMAND

    async def edit_text(self, update: Update, _: CallbackContext) -> int:
        message = update.message
        await message.reply_text("请回复替换的文本")
        return self.GET_TEXT

    async def get_edit_text(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.message
        post_handler_data.post_text = message.text_markdown_v2
        await message.reply_text("替换成功")
        text = "请选择你的操作"
        reply_keyboard = [["推送频道", "添加TAG"], ["编辑文字", "删除图片"], ["退出"]]
        await message.reply_text(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.CHECK_COMMAND

    @staticmethod
    async def send_post(update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.message
        if update.message.text == "退出":
            await message.reply_text(text="退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("正在推送", reply_markup=ReplyKeyboardRemove())
        channel_id = post_handler_data.channel_id
        channel_name = None
        try:
            for channel_info in config.TELEGRAM["channel"]["POST"]:
                if post_handler_data.channel_id == channel_info["chat_id"]:
                    channel_name = channel_info["name"]
        except KeyError as error:
            Log.error("从配置文件获取频道信息发生错误，退出任务", error)
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
        except (BadRequest, TypeError) as error:
            await message.reply_text("图片获取错误，错误信息已经写到日记", reply_markup=ReplyKeyboardRemove())
            Log.error("Post模块图片获取错误", error)
            return ConversationHandler.END
        await message.reply_text("推送成功", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
