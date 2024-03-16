import json
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, TYPE_CHECKING, Dict

from httpx import Timeout
from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import ConversationHandler, filters

from core.config import config
from core.plugin import Plugin, conversation, handler
from modules.apihelper.client.components.hyperion import Hyperion
from modules.apihelper.error import APIHelperException
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update, Message
    from telegram.ext import ContextTypes, Job
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
        self.channel_msg: Optional["Message"] = None
        self.need_update: bool = False
        self.end_task_time: datetime = self.utc_8(datetime.now() + timedelta(hours=1))

    def need_end_task(self) -> bool:
        if not self.real_need_update():
            return True
        now = self.utc_8(datetime.now())
        out_of_time = now >= self.end_task_time
        if out_of_time:
            logger.warning("PostCode 定时任务超过最大允许时间，结束任务")
        return out_of_time

    @staticmethod
    def utc_8(time: datetime) -> datetime:
        return time.astimezone(timezone(timedelta(hours=8)))

    def get_end_time(self) -> str:
        for code in self.hoyo_code:
            if code.offline_at:
                utc_8 = self.utc_8(code.offline_at)
                return utc_8.strftime("%Y-%m-%d %H:%M:%S")
        return "未知时间"

    def get_guess_last_time(self) -> datetime:
        return self.utc_8(self.mys_code[-1].to_get_time)

    def get_need_update_text(self):
        time = []
        for code in self.mys_code:
            time.append(self.utc_8(code.to_get_time).strftime("%H:%M:%S"))
        return UPDATE_TEMPLATE % tuple(time)

    def real_need_update(self) -> bool:
        return not all([i.code for i in self.mys_code] + [i.exchange_code for i in self.hoyo_code])

    def get_code_text(self) -> List[str]:
        return [code.text for code in self.mys_code] + [code.text for code in self.hoyo_code]

    def have_changes(self, mys_code: List["LiveCode"], hoyo_code: List["LiveCodeHoYo"]) -> bool:
        if len(mys_code) != len(self.mys_code) or len(hoyo_code) != len(self.hoyo_code):
            return True
        for i, code in enumerate(mys_code):
            if code.code != self.mys_code[i].code:
                return True
        for i, code in enumerate(hoyo_code):
            if code.exchange_code != self.hoyo_code[i].exchange_code:
                return True
        return False

    def get_text(self) -> str:
        return POST_TEMPLATE % (
            self.version,
            *self.get_code_text(),
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
UPDATE_TEMPLATE = """可能的兑换码发放时间：

%s、%s、%s

更新可能延迟三到五分钟，请耐心等待。"""


class PostCode(Plugin.Conversation):
    """版本前瞻特别节目兑换码推送"""

    MENU_KEYBOARD = ReplyKeyboardMarkup([["推送频道", "推送并且定时更新"], ["退出"]], True, True)
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
            ),
        )

    def init_version(self, news: List[Dict]) -> Tuple[Optional[str], Optional[Dict]]:
        for new in news:
            post = new.get("post", {})
            if not post:
                continue
            if not (subject := post.get("subject")):
                continue
            if not (match := self.SUBJECT_RE.findall(subject)):
                continue
            return match[0], post
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
            if len(post_code_handler_data.mys_code) != 3:
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
        post_code_handler_data: PostCodeHandlerData = context.chat_data.get("post_code_handler_data")
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "推送频道":
            return await self.get_channel(update, context)
        if message.text == "推送并且定时更新":
            if not post_code_handler_data.real_need_update():
                await message.reply_text(
                    "所有兑换码已发放，无需创建更新任务，将直接推送。", reply_markup=ReplyKeyboardRemove()
                )
                return await self.get_channel(update, context)
            post_code_handler_data.need_update = True
            await message.reply_text(post_code_handler_data.get_need_update_text())
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
            msg = await context.bot.send_message(channel_id, post_text, parse_mode=ParseMode.HTML)
            if post_code_handler_data.need_update:
                post_code_handler_data.channel_msg = msg
                end_time = post_code_handler_data.get_guess_last_time() + timedelta(minutes=10)
                post_code_handler_data.end_task_time = end_time
                self.create_task(post_code_handler_data)
        except BadRequest as exc:
            await message.reply_text(f"发送消息时发生错误 {exc.message}", reply_markup=ReplyKeyboardRemove())
            logger.error("PostCode 模块发送消息时发生错误 %s", exc.message)
            return ConversationHandler.END
        await message.reply_text("推送成功", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def create_task(self, data: "PostCodeHandlerData"):
        logger.debug("创建 PostCode 定时任务")
        self.application.job_queue.run_once(self.post_code_task, 60, data=data)

    async def post_code_task(self, context: "ContextTypes.DEFAULT_TYPE"):
        client = self.get_bbs_client()
        job: "Job" = context.job
        if not isinstance(job.data, PostCodeHandlerData):
            return
        post_code_handler_data: "PostCodeHandlerData" = job.data
        if not post_code_handler_data.channel_msg:
            return
        act_id = post_code_handler_data.act_id
        ver_code = post_code_handler_data.ver_code
        channel_username = post_code_handler_data.channel_username
        try:
            mys_code = await client.get_live_code(act_id, ver_code)
            hoyo_code = await client.get_live_code_hoyo(self.gids)
            if len(post_code_handler_data.mys_code) != 3:
                raise ValueError("获取兑换码数据成功，但是数量不对")
            if post_code_handler_data.have_changes(mys_code, hoyo_code):
                post_code_handler_data.mys_code = mys_code
                post_code_handler_data.hoyo_code = hoyo_code
                post_text = post_code_handler_data.get_text()
                post_text += f"\n\n@{channel_username}"
                await post_code_handler_data.channel_msg.edit_text(post_text, parse_mode=ParseMode.HTML)
                logger.success("PostCode 兑换码发生变化，已更新频道消息")
            else:
                logger.debug("PostCode 兑换码未发生变化")
        except (APIHelperException, ValueError) as exc:
            logger.error("获取兑换码时发生错误 %s", str(exc))
        except BadRequest as exc:
            logger.error("自动更新兑换码消息失败 Message[%s]", exc.message)
        except Forbidden as exc:
            logger.error("自动更新兑换码消息失败 message[%s]", exc.message)
        except Exception as exc:
            logger.error("自动更新兑换码消息失败", exc_info=exc)
        if post_code_handler_data.need_end_task():
            logger.success("PostCode 定时任务结束")
        else:
            self.create_task(post_code_handler_data)
