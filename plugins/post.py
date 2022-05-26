from typing import Optional, List
from bs4 import BeautifulSoup

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ConversationHandler
from telegram.helpers import escape_markdown

from config import config
from logger import Log
from model.genshinhelper import Mihoyo, ArtworkImage
from plugins.base import BasePlugins
from service import BaseService


class PostHandlerData:
    def __init__(self):
        self.post_text: str = ""
        self.post_images: Optional[List[ArtworkImage]] = None


class Post(BasePlugins):
    CHECK_POST, SEND_POST = range(10900, 10902)

    def __init__(self, service: BaseService):
        super().__init__(service)
        self.bbs = Mihoyo()

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
            await message.reply_text(f"获取作品ID错误，请检查连接是否合法", reply_markup=ReplyKeyboardRemove())
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
            Log.error("Post模块图片获取错误 \n", error)
            return ConversationHandler.END
        post_handler_data.post_text = post_text
        post_handler_data.post_images = post_images
        text = "请选择你推送到的频道"
        reply_keyboard = [['默认频道'], ['退出']]
        await message.reply_text(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.SEND_POST

    async def send_post(self, update: Update, context: CallbackContext) -> int:
        post_handler_data: PostHandlerData = context.chat_data.get("post_handler_data")
        message = update.message
        if update.message.text == "退出":
            await message.reply_text(text="退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("正在推送", reply_markup=ReplyKeyboardRemove())
        try:
            channel_name = config.TELEGRAM["channel"]["POST"]["name"]
            channel_id = config.TELEGRAM["channel"]["POST"]["char_id"]
        except KeyError as error:
            Log.error("从配置文件获取频道信息发生错误，退出任务 \n", error)
            await message.reply_text("从配置文件获取频道信息发生错误，退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        post_text = post_handler_data.post_text
        post_images = post_handler_data.post_images
        post_text += f" @{channel_name}"
        try:
            if len(post_images) > 1:
                media = [InputMediaPhoto(img_info.data) for img_info in post_images]
                media[0] = InputMediaPhoto(post_images[0].data, caption=post_text, parse_mode=ParseMode.MARKDOWN_V2)
                await context.bot.send_media_group(channel_id, media=media)
            elif len(post_images) == 1:
                image = post_images[0]
                await context.bot.send_photo(channel_id, photo=image.data, caption=post_text,
                                             parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await message.reply_text("图片获取错误", reply_markup=ReplyKeyboardRemove())  # excuse?
                return ConversationHandler.END
        except (BadRequest, TypeError) as error:
            await message.reply_text("图片获取错误，错误信息已经写到日记", reply_markup=ReplyKeyboardRemove())
            Log.error("Post模块图片获取错误 \n", error)
            return ConversationHandler.END
        await message.reply_text("推送成功", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
