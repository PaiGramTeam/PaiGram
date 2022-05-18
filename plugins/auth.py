import time
import datetime
import random
from typing import Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext
from numpy.random import Generator, MT19937
from telegram.helpers import escape_markdown

from logger import Log
from model.helpers import get_admin_list
from service import BaseService

FullChatPermissions = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=True,
    can_invite_users=True,
    can_pin_messages=True,
)


class Auth:
    def __init__(self, service: BaseService):
        self.service = service
        self.send_time = time.time()
        self.generator = Generator(MT19937(int(self.send_time)))
        self.time_out = 120
        self.kick_time = 120

    def random(self, low: int, high: int) -> int:
        if self.send_time + 24 * 60 * 60 >= time.time():
            self.send_time = time.time()
            self.generator = Generator(MT19937(int(self.send_time)))
        return int(self.generator.uniform(low, high))

    async def kick(self, context: CallbackContext, chat_id: int, user_id: int) -> bool:
        if await context.bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                until_date=int(time.time()) + self.kick_time,
        ):
            return True
        else:
            return False

    async def clean(self, context: CallbackContext, chat_id: int, user_id: int, message_id: int) -> bool:
        if await context.bot.delete_message(chat_id=chat_id, message_id=message_id):
            return True
        else:
            return False

    async def restore(self, context: CallbackContext, chat_id: int, user_id: int) -> bool:
        if await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=FullChatPermissions,

        ):
            return True
        else:
            return False

    async def admin(self, update: Update, context: CallbackContext) -> None:
        async def admin_callback(callback_query_data: str) -> Tuple[bool, int]:
            _data = callback_query_data.split("|")
            if _data[1] == "pass":
                _result = True
            else:
                _result = False
            _user_id = int(_data[2])
            return _result, _user_id

        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message
        chat = message.chat
        Log.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 点击Auth管理员命令")
        if user.id not in await get_admin_list(
                bot=context.bot,
                cache=self.service.cache,
                chat_id=chat.id,
                extra_user=[]
        ):
            await callback_query.answer(text=f"你不是管理！\n"
                                             f"再瞎几把点我叫西风骑士团、千岩军和天领奉行了！", show_alert=True)
            return
        result, user_id = await admin_callback(callback_query.data)
        try:
            member_info = await context.bot.get_chat_member(chat.id, user_id)
        except BadRequest as error:
            Log.warning(f"获取用户 {user_id} 在群 {chat.title}[{chat.id}] 信息失败 \n", error)
            user_info = f"{user_id}"
        else:
            user_info = member_info.user.mention_markdown_v2()

        if result:
            await callback_query.answer(text="放行", show_alert=False)
            await self.restore(context, chat.id, user_id)
            if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user_id}|clean_join"):
                schedule.remove()
            await message.edit_text(f"{user_info} 被 {user.mention_markdown_v2()} 放行",
                                    parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await callback_query.answer(text="驱离", show_alert=False)
            await self.kick(context, chat.id, user_id)
            await message.edit_text(f"{user_info} 被 {user.mention_markdown_v2()} 驱离",
                                    parse_mode=ParseMode.MARKDOWN_V2)
        if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user_id}|auth_kick"):
            schedule.remove()

    async def query(self, update: Update, context: CallbackContext) -> None:

        async def query_callback(callback_query_data: str) -> Tuple[int, bool, str, str]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _question_id = int(_data[2])
            _answer_id = int(_data[3])
            _answer = await self.service.quiz_service.get_answer(_answer_id)
            _question = await self.service.quiz_service.get_question(_question_id)
            _result = _answer["is_correct"]
            _answer_encode = _answer["answer"]
            _question_encode = _question["question"]
            return _user_id, _result, _question_encode, _answer_encode

        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message
        chat = message.chat
        user_id, result, question, answer = await query_callback(callback_query.data)
        Log.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 点击Auth认证命令 ")
        if user.id != user_id:
            await callback_query.answer(text=f"这不是你的验证！\n"
                                             f"再瞎几把点再按我叫西风骑士团、千岩军和天领奉行了！", show_alert=True)
            return
        Log.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 认证结果为 {result}")
        if result:
            await callback_query.answer(text="验证成功", show_alert=False)
            await self.restore(context, chat.id, user_id)
            if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user.id}|clean_join"):
                schedule.remove()
            text = f"{user.mention_markdown_v2()} 验证成功，向着星辰与深渊！\n" \
                   f"问题：{escape_markdown(question, version=2)} \n" \
                   f"回答：{escape_markdown(answer, version=2)}"
        else:
            await callback_query.answer(text=f"验证失败，请在 {self.time_out} 秒后重试", show_alert=True)
            await self.kick(context, chat.id, user_id)
            text = f"{user.mention_markdown_v2()} 验证失败，已经赶出提瓦特大陆！\n" \
                   f"问题：{escape_markdown(question, version=2)} \n" \
                   f"回答：{escape_markdown(answer, version=2)}"
        try:
            await message.edit_text(text, parse_mode=ParseMode.MARKDOWN_V2)
        except BadRequest as exc:
            if 'are exactly the same as ' in str(exc):
                Log.warning("编辑消息发生异常，可能为用户点按多次键盘导致，错误信息为 \n", exc)
                pass
            else:
                raise exc
        if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user.id}|auth_kick"):
            schedule.remove()

    async def new_mem(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        chat = message.chat
        for user in message.new_chat_members:
            if user.id == context.bot.id:
                return
            Log.info(f"用户 {user.full_name}[{user.id}] 尝试加入群 {chat.title}[{chat.id}]")
        if message.from_user.id in await get_admin_list(
                bot=context.bot,
                cache=self.service.cache,
                chat_id=chat.id,
                extra_user=[]
        ):
            await message.reply_text("派蒙检测到管理员邀请，自动放行了！")
            return
        for user in message.new_chat_members:
            if user.is_bot:
                continue
            try:
                await context.bot.restrict_chat_member(chat_id=message.chat.id, user_id=user.id,
                                                       permissions=ChatPermissions(can_send_messages=False))
            except BadRequest as err:
                if "Not enough rights" in str(err):
                    Log.warning(f"权限不够 char_id[{message.chat_id}]", err)
                    await message.reply_markdown_v2(f"派蒙无法修改 {user.mention_markdown_v2()} 的权限！"
                                                    f"请检查是否给派蒙授权管理了")
                    return
                else:
                    raise err
            question_id_list = await self.service.quiz_service.get_question_id_list()
            if len(question_id_list) == 0:
                await message.reply_text(f"旅行者！！！派蒙的问题清单你还没给我！！快去私聊我给我问题！")
                return
            index = self.random(0, len(question_id_list))
            question = await self.service.quiz_service.get_question(question_id_list[index])
            options = []
            for answer_id in question["answer_id"]:
                answer = await self.service.quiz_service.get_answer(answer_id)
                options.append(answer)
            random.shuffle(options)
            buttons = [
                [
                    InlineKeyboardButton(
                        answer["answer"],
                        callback_data=f"auth_challenge|{user.id}|{question['question_id']}|{answer['answer_id']}",
                    )
                ]
                for answer in options
            ]
            random.shuffle(buttons)
            buttons.append(
                [
                    InlineKeyboardButton(
                        "放行",
                        callback_data=f"auth_admin|pass|{user.id}",
                    ),
                    InlineKeyboardButton(
                        "驱离",
                        callback_data=f"auth_admin|kick|{user.id}",
                    ),
                ]
            )
            reply_message = f"*欢迎来到「提瓦特」世界！* \n" \
                            f"问题: {escape_markdown(question['question'], version=2)} \n" \
                            f"请在 {self.time_out} 内回答问题"
            try:
                question_message = await message.reply_markdown_v2(reply_message,
                                                                   reply_markup=InlineKeyboardMarkup(buttons))
            except BadRequest as er:
                await message.reply_text("派蒙分心了一下，不小心忘记你了，你只能先退出群再进来吧。")
                raise er

            context.job_queue.scheduler.add_job(self.kick, "date", id=f"{chat.id}|{user.id}|auth_kick",
                                                name=f"{chat.id}|{user.id}|auth_kick", args=[context, chat.id, user.id],
                                                run_date=context.job_queue._tz_now() + datetime.timedelta(
                                                    seconds=self.time_out), replace_existing=True)
            context.job_queue.scheduler.add_job(self.clean, "date", id=f"{message.chat.id}|{user.id}|auth_clean_join",
                                                name=f"{message.chat.id}|{user.id}|auth_clean_join",
                                                args=[context, message.chat.id, user.id, message.message_id],
                                                run_date=context.job_queue._tz_now() + datetime.timedelta(
                                                    seconds=self.time_out), replace_existing=True)
            context.job_queue.scheduler.add_job(self.clean, "date",
                                                id=f"{message.chat.id}|{user.id}|auth_clean_question",
                                                name=f"{message.chat.id}|{user.id}|auth_clean_question",
                                                args=[context, message.chat.id, user.id, question_message.message_id],
                                                run_date=context.job_queue._tz_now() + datetime.timedelta(
                                                    seconds=self.time_out), replace_existing=True)
