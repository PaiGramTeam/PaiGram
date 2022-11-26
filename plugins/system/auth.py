import asyncio
import random
import time
from typing import Dict, List, Tuple, Union

from telegram import (ChatMember, ChatPermissions, InlineKeyboardButton,
                      InlineKeyboardMarkup, Update)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CallbackQueryHandler
from telegram.helpers import escape_markdown

from core.base.mtproto import MTProto
from core.bot import bot
from core.plugin import Plugin, handler
from core.quiz import QuizService
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger

try:
    from pyrogram.errors import BadRequest as MTPBadRequest
    from pyrogram.errors import FloodWait as MTPFloodWait

    PYROGRAM_AVAILABLE = True
except ImportError:
    PYROGRAM_AVAILABLE = False

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


class GroupJoiningVerification(Plugin):
    """群验证模块"""

    def __init__(self, quiz_service: QuizService = None, mtp: MTProto = None):
        self.quiz_service = quiz_service
        self.time_out = 120
        self.kick_time = 120
        self.lock = asyncio.Lock()
        self.chat_administrators_cache: Dict[Union[str, int], Tuple[float, List[ChatMember]]] = {}
        self.is_refresh_quiz = False
        self.mtp = mtp.client

    async def __async_init__(self):
        logger.info("群验证模块正在刷新问题列表")
        await self.refresh_quiz()
        logger.success("群验证模块刷新问题列表成功")

    async def refresh_quiz(self):
        async with self.lock:
            if not self.is_refresh_quiz:
                await self.quiz_service.refresh_quiz()
                self.is_refresh_quiz = True

    async def get_chat_administrators(self, context: CallbackContext, chat_id: Union[str, int]) -> List[ChatMember]:
        async with self.lock:
            cache_data = self.chat_administrators_cache.get(f"{chat_id}")
            if cache_data is not None:
                cache_time, chat_administrators = cache_data
                if time.time() >= cache_time + 360:
                    return chat_administrators
            chat_administrators = await context.bot.get_chat_administrators(chat_id)
            self.chat_administrators_cache[f"{chat_id}"] = (time.time(), chat_administrators)
            return chat_administrators

    @staticmethod
    def is_admin(chat_administrators: List[ChatMember], user_id: int) -> bool:
        return any(admin.user.id == user_id for admin in chat_administrators)

    async def kick_member_job(self, context: CallbackContext):
        job = context.job
        logger.info(f"踢出用户 user_id[{job.user_id}] 在 chat_id[{job.chat_id}]")
        try:
            await context.bot.ban_chat_member(
                chat_id=job.chat_id, user_id=job.user_id, until_date=int(time.time()) + self.kick_time
            )
        except BadRequest as exc:
            logger.error(f"Auth模块在 chat_id[{job.chat_id}] user_id[{job.user_id}] 执行kick失败")
            logger.exception(exc)

    @staticmethod
    async def clean_message_job(context: CallbackContext):
        job = context.job
        logger.debug(f"删除消息 chat_id[{job.chat_id}] 的 message_id[{job.data}]")
        try:
            await context.bot.delete_message(chat_id=job.chat_id, message_id=job.data)
        except BadRequest as exc:
            if "not found" in str(exc):
                logger.warning(f"Auth模块删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败 消息不存在")
            elif "Message can't be deleted" in str(exc):
                logger.warning(f"Auth模块删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败 消息无法删除 可能是没有授权")
            else:
                logger.error(f"Auth模块删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败")
                logger.exception(exc)

    @staticmethod
    async def restore_member(context: CallbackContext, chat_id: int, user_id: int):
        logger.debug(f"重置用户权限 user_id[{user_id}] 在 chat_id[{chat_id}]")
        try:
            await context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=FullChatPermissions)
        except BadRequest as exc:
            logger.error(f"Auth模块在 chat_id[{chat_id}] user_id[{user_id}] 执行restore失败")
            logger.exception(exc)

    @handler(CallbackQueryHandler, pattern=r"^auth_admin\|", block=False)
    @error_callable
    @restricts(without_overlapping=True)
    async def admin(self, update: Update, context: CallbackContext) -> None:
        async def admin_callback(callback_query_data: str) -> Tuple[str, int]:
            _data = callback_query_data.split("|")
            _result = _data[1]
            _user_id = int(_data[2])
            logger.debug(f"admin_callback函数返回 result[{_result}] user_id[{_user_id}]")
            return _result, _user_id

        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message
        chat = message.chat
        logger.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 点击Auth管理员命令")
        chat_administrators = await self.get_chat_administrators(context, chat_id=chat.id)
        if not self.is_admin(chat_administrators, user.id):
            logger.debug(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 非群管理")
            await callback_query.answer(text="你不是管理！\n" "再乱点我叫西风骑士团、千岩军和天领奉行了！", show_alert=True)
            return
        result, user_id = await admin_callback(callback_query.data)
        try:
            member_info = await context.bot.get_chat_member(chat.id, user_id)
        except BadRequest as error:
            logger.warning(f"获取用户 {user_id} 在群 {chat.title}[{chat.id}] 信息失败 \n", error)
            user_info = f"{user_id}"
        else:
            user_info = member_info.user.mention_markdown_v2()

        if result == "pass":
            await callback_query.answer(text="放行", show_alert=False)
            await self.restore_member(context, chat.id, user_id)
            if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user_id}|auth_kick"):
                schedule.remove()
            await message.edit_text(f"{user_info} 被 {user.mention_markdown_v2()} 放行", parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f"用户 user_id[{user_id}] 在群 {chat.title}[{chat.id}] 被管理放行")
        elif result == "kick":
            await callback_query.answer(text="驱离", show_alert=False)
            await context.bot.ban_chat_member(chat.id, user_id)
            await message.edit_text(f"{user_info} 被 {user.mention_markdown_v2()} 驱离", parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f"用户 user_id[{user_id}] 在群 {chat.title}[{chat.id}] 被管理踢出")
        elif result == "unban":
            await callback_query.answer(text="解除驱离", show_alert=False)
            await self.restore_member(context, chat.id, user_id)
            if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user_id}|auth_kick"):
                schedule.remove()
            await message.edit_text(
                f"{user_info} 被 {user.mention_markdown_v2()} 解除驱离", parse_mode=ParseMode.MARKDOWN_V2
            )
            logger.info(f"用户 user_id[{user_id}] 在群 {chat.title}[{chat.id}] 被管理解除封禁")
        else:
            logger.warning(f"auth 模块 admin 函数 发现未知命令 result[{result}]")
            await context.bot.send_message(chat.id, "派蒙这边收到了错误的消息！请检查详细日记！")
        if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user_id}|auth_kick"):
            schedule.remove()

    @handler(CallbackQueryHandler, pattern=r"^auth_challenge\|", block=False)
    @error_callable
    @restricts(without_overlapping=True)
    async def query(self, update: Update, context: CallbackContext) -> None:
        async def query_callback(callback_query_data: str) -> Tuple[int, bool, str, str]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _question_id = int(_data[2])
            _answer_id = int(_data[3])
            _answer = await self.quiz_service.get_answer(_answer_id)
            _question = await self.quiz_service.get_question(_question_id)
            _result = _answer.is_correct
            _answer_encode = _answer.text
            _question_encode = _question.text
            logger.debug(
                f"query_callback函数返回 user_id[{_user_id}] result[{_result}] \n"
                f"question_encode[{_question_encode}] answer_encode[{_answer_encode}]"
            )
            return _user_id, _result, _question_encode, _answer_encode

        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message
        chat = message.chat
        user_id, result, question, answer = await query_callback(callback_query.data)
        logger.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 点击Auth认证命令 ")
        if user.id != user_id:
            await callback_query.answer(text="这不是你的验证！\n" "再乱点再按我叫西风骑士团、千岩军和天领奉行了！", show_alert=True)
            return
        logger.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 认证结果为 {'通过' if result else '失败'}")
        if result:
            buttons = [[InlineKeyboardButton("驱离", callback_data=f"auth_admin|kick|{user.id}")]]
            await callback_query.answer(text="验证成功", show_alert=False)
            await self.restore_member(context, chat.id, user_id)
            if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user.id}|auth_kick"):
                schedule.remove()
            text = (
                f"{user.mention_markdown_v2()} 验证成功，向着星辰与深渊！\n"
                f"问题：{escape_markdown(question, version=2)} \n"
                f"回答：{escape_markdown(answer, version=2)}"
            )
            logger.info(f"用户 user_id[{user_id}] 在群 {chat.title}[{chat.id}] 验证成功")
        else:
            buttons = [
                [
                    InlineKeyboardButton("驱离", callback_data=f"auth_admin|kick|{user.id}"),
                    InlineKeyboardButton("撤回驱离", callback_data=f"auth_admin|unban|{user.id}"),
                ]
            ]
            await callback_query.answer(text=f"验证失败，请在 {self.time_out} 秒后重试", show_alert=True)
            await asyncio.sleep(3)
            await context.bot.ban_chat_member(
                chat_id=chat.id, user_id=user_id, until_date=int(time.time()) + self.kick_time
            )
            text = (
                f"{user.mention_markdown_v2()} 验证失败，已经赶出提瓦特大陆！\n"
                f"问题：{escape_markdown(question, version=2)} \n"
                f"回答：{escape_markdown(answer, version=2)}"
            )
            logger.info(f"用户 user_id[{user_id}] 在群 {chat.title}[{chat.id}] 验证失败")
        try:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN_V2)
        except BadRequest as exc:
            if "are exactly the same as " in str(exc):
                logger.warning("编辑消息发生异常，可能为用户点按多次键盘导致")
            else:
                raise exc
        if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user.id}|auth_kick"):
            schedule.remove()

    @handler.message.new_chat_members(priority=2)
    @error_callable
    async def new_mem(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        chat = message.chat
        if len(bot.config.verify_groups) >= 1:
            for verify_group in bot.config.verify_groups:
                if verify_group == chat.id:
                    break
            else:
                return
        else:
            return
        for user in message.new_chat_members:
            if user.id == context.bot.id:
                return
            logger.info(f"用户 {user.full_name}[{user.id}] 尝试加入群 {chat.title}[{chat.id}]")
        not_enough_rights = context.chat_data.get("not_enough_rights", False)
        if not_enough_rights:
            return
        chat_administrators = await self.get_chat_administrators(context, chat_id=chat.id)
        if self.is_admin(chat_administrators, message.from_user.id):
            await message.reply_text("派蒙检测到管理员邀请，自动放行了！")
            return
        for user in message.new_chat_members:
            if user.is_bot:
                continue
            question_id_list = await self.quiz_service.get_question_id_list()
            if len(question_id_list) == 0:
                await message.reply_text("旅行者！！！派蒙的问题清单你还没给我！！快去私聊我给我问题！")
                return
            try:
                await context.bot.restrict_chat_member(
                    chat_id=message.chat.id, user_id=user.id, permissions=ChatPermissions(can_send_messages=False)
                )
            except BadRequest as err:
                if "Not enough rights" in str(err):
                    logger.warning(f"权限不够 chat_id[{message.chat_id}]")
                    # reply_message = await message.reply_markdown_v2(f"派蒙无法修改 {user.mention_markdown_v2()} 的权限！"
                    #                                                 f"请检查是否给派蒙授权管理了")
                    context.chat_data["not_enough_rights"] = True
                    # await context.bot.delete_message(chat.id, reply_message.message_id)
                    return
                else:
                    raise err
            question_id = random.choice(question_id_list)  # nosec
            question = await self.quiz_service.get_question(question_id)
            buttons = [
                [
                    InlineKeyboardButton(
                        answer.text,
                        callback_data=f"auth_challenge|{user.id}|{question['question_id']}|{answer['answer_id']}",
                    )
                ]
                for answer in question.answers
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
            reply_message = (
                f"*欢迎来到「提瓦特」世界！* \n" f"问题: {escape_markdown(question.text, version=2)} \n" f"请在 {self.time_out}S 内回答问题"
            )
            logger.debug(
                f"发送入群验证问题 question_id[{question.question_id}] question[{question.text}] \n"
                f"给{user.full_name}[{user.id}] 在 {chat.title}[{chat.id}]"
            )
            try:
                question_message = await message.reply_markdown_v2(
                    reply_message, reply_markup=InlineKeyboardMarkup(buttons)
                )
            except BadRequest as exc:
                await message.reply_text("派蒙分心了一下，不小心忘记你了，你只能先退出群再重新进来吧。")
                raise exc
            context.job_queue.run_once(
                callback=self.kick_member_job,
                when=self.time_out,
                name=f"{chat.id}|{user.id}|auth_kick",
                chat_id=chat.id,
                user_id=user.id,
                job_kwargs={"replace_existing": True, "id": f"{chat.id}|{user.id}|auth_kick"},
            )
            context.job_queue.run_once(
                callback=self.clean_message_job,
                when=self.time_out,
                data=message.message_id,
                name=f"{chat.id}|{user.id}|auth_clean_join_message",
                chat_id=chat.id,
                user_id=user.id,
                job_kwargs={"replace_existing": True, "id": f"{chat.id}|{user.id}|auth_clean_join_message"},
            )
            context.job_queue.run_once(
                callback=self.clean_message_job,
                when=self.time_out,
                data=question_message.message_id,
                name=f"{chat.id}|{user.id}|auth_clean_question_message",
                chat_id=chat.id,
                user_id=user.id,
                job_kwargs={"replace_existing": True, "id": f"{chat.id}|{user.id}|auth_clean_question_message"},
            )
            if PYROGRAM_AVAILABLE and self.mtp and (question_message.id - message.id - 1):
                try:
                    messages_list = await self.mtp.get_messages(
                        chat.id, message_ids=list(range(message.id + 1, question_message.id))
                    )
                    for find_message in messages_list:
                        if find_message.empty:
                            continue
                        if find_message.from_user and find_message.from_user.id == user.id:
                            await self.mtp.delete_messages(chat_id=chat.id, message_ids=find_message.id)
                            if find_message.text is not None and "@" in find_message.text:
                                await context.bot.ban_chat_member(chat.id, user.id)
                                button = [[InlineKeyboardButton("解除封禁", callback_data=f"auth_admin|pass|{user.id}")]]
                                text = f"{user.full_name} 由于加入群组后，" "在验证缝隙间发送了带有 @(Mention) 的消息，已被踢出群组，并加入了封禁列表。"
                                await question_message.edit_text(text, reply_markup=InlineKeyboardMarkup(button))
                                if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user.id}|auth_kick"):
                                    schedule.remove()
                            logger.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 验证缝隙间发送消息" "现已删除")
                except BadRequest as exc:
                    logger.error(f"后验证处理中发生错误 {repr(exc)}")
                    logger.exception(exc)
                except MTPFloodWait:
                    logger.warning("调用 mtp 触发洪水限制")
                except MTPBadRequest as exc:
                    logger.error("调用 mtp 请求错误")
                    logger.exception(exc)
