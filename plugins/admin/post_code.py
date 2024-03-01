import json
import re
from datetime import timezone, timedelta
from typing import List, Optional, Tuple, TYPE_CHECKING, Dict

from httpx import Timeout
from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ConversationHandler, filters

from core.config import config
from core.plugin import Plugin, conversation, handler
from modules.apihelper.client.components.hyperion import Hyperion
from modules.apihelper.error import APIHelperException
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes
    from modules.apihelper.models.genshin.hyperion import LiveCode, LiveCodeHoYo


class PostCodeHandlerData:
    def __init__(self):
        self.version: str = ""
        self.act_id = ""
        self.ver_code = ""
        self.mys_code: List["LiveCode"] = []
        self.hoyo_code: List["LiveCodeHoYo"] = []
        self.channel_username: str = ""
        self.channel_id: int = -1

    def get_end_time(self) -> str:
        for code in self.hoyo_code:
            if code.offline_at:
                utc_8 = code.offline_at.astimezone(timezone(timedelta(hours=8)))
                return utc_8.strftime("%Y-%m-%d %H:%M:%S")

    def get_text(self) -> str:
        return POST_TEMPLATE % (
            self.version,
            self.mys_code[0].text,
            self.mys_code[1].text,
            self.mys_code[2].text,
            self.hoyo_code[0].text,
            self.hoyo_code[1].text,
            self.hoyo_code[2].text,
            self.get_end_time(),
        )


SEND_POST, CHECK_COMMAND, GET_POST_CHANNEL = range(10900, 10903)
POST_TEMPLATE = """<b>《原神》%s 版本前瞻特别节目兑换码</b>

国服：
<code>%s</code> - 原石 ×100，精锻用魔矿 x10
<code>%s</code> - 原石 ×100，大英雄的经验 x5
<code>%s</code> - 原石 ×100，摩拉 x50000

国际服：
<code>%s</code> - 原石 ×100，精锻用魔矿 x10
<code>%s</code> - 原石 ×100，大英雄的经验 x5
<code>%s</code> - 原石 ×100，摩拉 x50000

兑换码过期时间 %s UTC+8，请尽快领取。"""


class PostCode(Plugin.Conversation):
    """版本前瞻特别节目兑换码推送"""

    MENU_KEYBOARD = ReplyKeyboardMarkup([["推送频道", "退出"]], True, True)
    SUBJECT_RE = re.compile(r"一起来看《原神》(\d+\.\d+)版本前瞻特别节目吧！")
    ACT_RE = re.compile(r"act_id=(.*?)&")

    def __init__(self):
        self.gids = 2
        self.type_id = 3

    @staticmethod
    def get_bbs_client() -> Hyperion:
        return Hyperion(
            timeout=Timeout(
                connect=config.connect_timeout,
                read=config.read_timeout,
                write=config.write_timeout,
                pool=config.pool_timeout,
            )
        )

    def init_version(self, news: List[Dict]) -> Tuple[Optional[str], Optional[Dict]]:
        for new in news:
            post = new.get("post", {})
            if not post:
                continue
            if not (subject := post.get("subject")):
                continue
            if not (match := self.SUBJECT_RE.match(subject)):
                continue
            return match.group(1), post
        return None, None

    def init_act_id(self, post: Dict) -> Optional[str]:
        structured_content = post.get("structured_content")
        if not structured_content:
            return None
        structured_data = json.loads(structured_content)
        for item in structured_data:
            if not (attributes := item.get("attributes")):
                continue
            if not (link := attributes.get("link")):
                continue
            if not (match := self.ACT_RE.search(link)):
                continue
            return match.group(1)
        return None

    async def init(self, post_code_handler_data: PostCodeHandlerData) -> bool:
        """解析 act_id ver_code 以及目标游戏版本"""
        client = self.get_bbs_client()
        try:
            news = await client.get_new_list(self.gids, self.type_id)
            version, final_post = self.init_version(news.get("list", []))
            if not final_post:
                raise ValueError("未找到版本前瞻特别节目文章")
            act_id = self.init_act_id(final_post)
            if not act_id:
                raise ValueError("未找到文章中的 act_id")
            live_info = await client.get_live_info(act_id)
            ver_code = live_info.code_ver
            post_code_handler_data.version = version
            post_code_handler_data.act_id = act_id
            post_code_handler_data.ver_code = ver_code
            post_code_handler_data.mys_code = await client.get_live_code(act_id, ver_code)
            post_code_handler_data.hoyo_code = await client.get_live_code_hoyo(self.gids)
            if len(post_code_handler_data.mys_code) != 3 or len(post_code_handler_data.hoyo_code) != 3:
                raise ValueError("获取兑换码数据成功，但是数量不对")
            return True
        finally:
            await client.close()

    @conversation.entry_point
    @handler.command(command="post_code", filters=filters.ChatType.PRIVATE, block=False, admin=True)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] POST_CODE 命令请求", user.full_name, user.id)
        post_code_handler_data = context.chat_data.get("post_code_handler_data")
        if post_code_handler_data is None:
            post_code_handler_data = PostCodeHandlerData()
            context.chat_data["post_code_handler_data"] = post_code_handler_data
        text = f"✿✿ヽ（°▽°）ノ✿ 你好！ {user.username} ，正在尝试自动获取必要的信息，请耐心等待。。。"
        reply = await message.reply_text(text)
        try:
            result = await self.init(post_code_handler_data)
            if not result:
                await reply.edit_text("初始化基础信息失败，请检查是否有直播正在进行")
                return ConversationHandler.END
            await reply.delete()
            await message.reply_text(post_code_handler_data.get_text(), parse_mode=ParseMode.HTML)
            await message.reply_text("初始化信息完成，请选择你的操作", reply_markup=self.MENU_KEYBOARD)
            return CHECK_COMMAND
        except (APIHelperException, ValueError) as exc:
            await reply.edit_text(f"初始化基础信息失败，错误信息：{str(exc)}")
            return ConversationHandler.END

    @conversation.state(state=CHECK_COMMAND)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def check_command(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "推送频道":
            return await self.get_channel(update, context)
        return ConversationHandler.END

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
        post_code_handler_data: PostCodeHandlerData = context.chat_data.get("post_code_handler_data")
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
        post_code_handler_data.channel_username = message.text
        post_code_handler_data.channel_id = channel_id
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("请核对你修改的信息", reply_markup=ReplyKeyboardMarkup(reply_keyboard, True, True))
        return SEND_POST

    @conversation.state(state=SEND_POST)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def send_post(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        post_code_handler_data: PostCodeHandlerData = context.chat_data.get("post_code_handler_data")
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text(text="退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("正在推送", reply_markup=ReplyKeyboardRemove())
        channel_id, channel_username = post_code_handler_data.channel_id, post_code_handler_data.channel_username
        post_text = post_code_handler_data.get_text()
        post_text += f"\n\n@{channel_username}"
        try:
            await context.bot.send_message(channel_id, post_text, parse_mode=ParseMode.HTML)
        except BadRequest as exc:
            await message.reply_text(f"发送消息时发生错误 {exc.message}", reply_markup=ReplyKeyboardRemove())
            logger.error("PostCode 模块发送消息时发生错误 %s", exc.message)
            return ConversationHandler.END
        await message.reply_text("推送成功", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
