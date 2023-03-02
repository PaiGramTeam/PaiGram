import asyncio
import random
import time
from typing import Tuple, Union, Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, ChatMember, Message, User
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CallbackQueryHandler, ChatMemberHandler, filters
from telegram.helpers import escape_markdown

from core.config import config
from core.dependence.mtproto import MTProto
from core.dependence.redisdb import RedisDB
from core.plugin import Plugin, handler
from core.services.quiz.services import QuizService
from utils.chatmember import extract_status_change
from utils.log import logger

try:
    from pyrogram.errors import BadRequest as MTPBadRequest, FloodWait as MTPFloodWait

    PYROGRAM_AVAILABLE = True
except ImportError:
    MTPBadRequest = ValueError
    MTPFloodWait = IndexError
    PYROGRAM_AVAILABLE = False

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib

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


class GroupCaptcha(Plugin):
    """群验证模块"""

    def __init__(self, quiz_service: QuizService = None, mtp: MTProto = None, redis: RedisDB = None):
        self.quiz_service = quiz_service
        self.time_out = 120
        self.kick_time = 120
        self.lock = asyncio.Lock()
        self.chat_administrators_cache: Dict[Union[str, int], Tuple[float, Tuple[ChatMember]]] = {}
        self.is_refresh_quiz = False
        self.mtp = mtp.client
        self.redis = redis.client

    async def initialize(self):
        logger.info("群验证模块正在刷新问题列表")
        await self.refresh_quiz()
        logger.success("群验证模块刷新问题列表成功")

    async def refresh_quiz(self):
        async with self.lock:
            if not self.is_refresh_quiz:
                await self.quiz_service.refresh_quiz()
                self.is_refresh_quiz = True

    async def get_chat_administrators(self, context: CallbackContext, chat_id: Union[str, int]) -> Tuple[ChatMember]:
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
    def is_admin(chat_administrators: Tuple[ChatMember], user_id: int) -> bool:
        return any(admin.user.id == user_id for admin in chat_administrators)

    async def kick_member_job(self, context: CallbackContext):
        job = context.job
        logger.info("踢出用户 user_id[%s] 在 chat_id[%s]", job.user_id, job.chat_id)
        try:
            await context.bot.ban_chat_member(
                chat_id=job.chat_id, user_id=job.user_id, until_date=int(time.time()) + self.kick_time
            )
        except BadRequest as exc:
            logger.error("GroupCaptcha插件在 chat_id[%s] user_id[%s] 执行kick失败", job.chat_id, job.user_id, exc_info=exc)

    @staticmethod
    async def clean_message_job(context: CallbackContext):
        job = context.job
        logger.debug("删除消息 chat_id[%s] 的 message_id[%s]", job.chat_id, job.data)
        try:
            await context.bot.delete_message(chat_id=job.chat_id, message_id=job.data)
        except BadRequest as exc:
            if "not found" in exc.message:
                logger.warning("GroupCaptcha插件删除消息 chat_id[%s] message_id[%s]失败 消息不存在", job.chat_id, job.data)
            elif "Message can't be deleted" in exc.message:
                logger.warning("GroupCaptcha插件删除消息 chat_id[%s] message_id[%s]失败 消息无法删除 可能是没有授权", job.chat_id, job.data)
            else:
                logger.error("GroupCaptcha插件删除消息 chat_id[%s] message_id[%s]失败", job.chat_id, job.data, exc_info=exc)

    @staticmethod
    async def restore_member(context: CallbackContext, chat_id: int, user_id: int):
        logger.debug("重置用户权限 user_id[%s] 在 chat_id[%s]", chat_id, user_id)
        try:
            await context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=FullChatPermissions)
        except BadRequest as exc:
            logger.error("GroupCaptcha插件在 chat_id[%s] user_id[%s] 执行restore失败", chat_id, user_id, exc_info=exc)

    async def get_new_chat_members_message(self, user: User, context: CallbackContext) -> Optional[Message]:
        qname = f"plugin:auth:new_chat_members_message:{user.id}"
        result = await self.redis.get(qname)
        if result:
            data = jsonlib.loads(str(result, encoding="utf-8"))
            return Message.de_json(data, context.bot)
        return None

    async def set_new_chat_members_message(self, user: User, message: Message):
        qname = f"plugin:auth:new_chat_members_message:{user.id}"
        await self.redis.set(qname, message.to_json(), ex=60)

    @handler(CallbackQueryHandler, pattern=r"^auth_admin\|", block=False)
    async def admin(self, update: Update, context: CallbackContext) -> None:
        async def admin_callback(callback_query_data: str) -> Tuple[str, int]:
            _data = callback_query_data.split("|")
            _result = _data[1]
            _user_id = int(_data[2])
            logger.debug("admin_callback函数返回 result[%s] user_id[%s]", _result, _user_id)
            return _result, _user_id

        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message
        chat = message.chat
        logger.info("用户 %s[%s] 在群 %s[%s] 点击Auth管理员命令", user.full_name, user.id, chat.title, chat.id)
        chat_administrators = await self.get_chat_administrators(context, chat_id=chat.id)
        if not self.is_admin(chat_administrators, user.id):
            logger.debug("用户 %s[%s] 在群 %s[%s] 非群管理", user.full_name, user.id, chat.title, chat.id)
            await callback_query.answer(text="你不是管理！\n" + config.notice.user_mismatch, show_alert=True)
            return
        result, user_id = await admin_callback(callback_query.data)
        try:
            member_info = await context.bot.get_chat_member(chat.id, user_id)
        except BadRequest as error:
            logger.warning("获取用户 %s 在群 %s[%s] 信息失败 \n %s", user_id, chat.title, chat.id, error.message)
            user_info = f"{user_id}"
        else:
            user_info = member_info.user.mention_markdown_v2()

        if result == "pass":
            await callback_query.answer(text="放行", show_alert=False)
            await self.restore_member(context, chat.id, user_id)
            if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user_id}|auth_kick"):
                schedule.remove()
            await message.edit_text(f"{user_info} 被 {user.mention_markdown_v2()} 放行", parse_mode=ParseMode.MARKDOWN_V2)
            logger.info("用户 %s[%s] 在群 %s[%s] 被管理放行", user.full_name, user.id, chat.title, chat.id)
        elif result == "kick":
            await callback_query.answer(text="驱离", show_alert=False)
            await context.bot.ban_chat_member(chat.id, user_id)
            await message.edit_text(f"{user_info} 被 {user.mention_markdown_v2()} 驱离", parse_mode=ParseMode.MARKDOWN_V2)
            logger.info("用户 %s[%s] 在群 %s[%s] 被管理踢出", user.full_name, user.id, chat.title, chat.id)
        elif result == "unban":
            await callback_query.answer(text="解除驱离", show_alert=False)
            await self.restore_member(context, chat.id, user_id)
            if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user_id}|auth_kick"):
                schedule.remove()
            await message.edit_text(
                f"{user_info} 被 {user.mention_markdown_v2()} 解除驱离", parse_mode=ParseMode.MARKDOWN_V2
            )
            logger.info("用户 user_id[%s] 在群 %s[%s] 被管理解除封禁", user_id, chat.title, chat.id)
        else:
            logger.warning("auth 模块 admin 函数 发现未知命令 result[%s]", result)
            await context.bot.send_message(chat.id, "派蒙这边收到了错误的消息！请检查详细日记！")
        if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user_id}|auth_kick"):
            schedule.remove()

    @handler(CallbackQueryHandler, pattern=r"^auth_challenge\|", block=False)
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
                "query_callback函数返回 user_id[%s] result[%s] \nquestion_encode[%s] answer_encode[%s]",
                _user_id,
                _result,
                _question_encode,
                _answer_encode,
            )
            return _user_id, _result, _question_encode, _answer_encode

        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message
        chat = message.chat
        user_id, result, question, answer = await query_callback(callback_query.data)
        logger.info("用户 %s[%s] 在群 %s[%s] 点击Auth认证命令", user.full_name, user.id, chat.title, chat.id)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的验证！\n" + config.notice.user_mismatch, show_alert=True)
            return
        logger.info(
            "用户 %s[%s] 在群 %s[%s] 认证结果为 %s", user.full_name, user.id, chat.title, chat.id, "通过" if result else "失败"
        )
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
            logger.info("用户 user_id[%s] 在群 %s[%s] 验证成功", user_id, chat.title, chat.id)
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
            logger.info("用户 user_id[%s] 在群 %s[%s] 验证失败", user_id, chat.title, chat.id)
        try:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN_V2)
        except BadRequest as exc:
            if "are exactly the same as " in exc.message:
                logger.warning("编辑消息发生异常，可能为用户点按多次键盘导致")
            else:
                raise exc
        if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user.id}|auth_kick"):
            schedule.remove()

    @handler.message(filters=filters.StatusUpdate.NEW_CHAT_MEMBERS, block=False)
    async def new_mem(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        chat = message.chat
        if len(config.verify_groups) >= 1:
            for verify_group in config.verify_groups:
                if verify_group == chat.id:
                    break
            else:
                return
        else:
            return
        for user in message.new_chat_members:
            if user.id == context.bot.id:
                return
            logger.debug("用户 %s[%s] 加入群 %s[%s]", user.full_name, user.id, chat.title, chat.id)
            await self.set_new_chat_members_message(user, message)

    @handler.chat_member(chat_member_types=ChatMemberHandler.CHAT_MEMBER, block=False)
    async def track_users(self, update: Update, context: CallbackContext) -> None:
        chat = update.effective_chat
        if len(config.verify_groups) >= 1:
            for verify_group in config.verify_groups:
                if verify_group == chat.id:
                    break
            else:
                return
        else:
            return
        new_chat_member = update.chat_member.new_chat_member
        from_user = update.chat_member.from_user
        user = new_chat_member.user
        result = extract_status_change(update.chat_member)
        if result is None:
            return
        was_member, is_member = result
        if was_member and not is_member:
            logger.info("用户 %s[%s] 退出群聊 %s[%s]", user.full_name, user.id, chat.title, chat.id)
            return
        if not was_member and is_member:
            logger.info("用户 %s[%s] 尝试加入群 %s[%s]", user.full_name, user.id, chat.title, chat.id)
            if user.is_bot:
                return
            chat_administrators = await self.get_chat_administrators(context, chat_id=chat.id)
            if self.is_admin(chat_administrators, from_user.id):
                await chat.send_message("派蒙检测到管理员邀请，自动放行了！")
                return
            question_id_list = await self.quiz_service.get_question_id_list()
            if len(question_id_list) == 0:
                await chat.send_message("旅行者！！！派蒙的问题清单你还没给我！！快去私聊我给我问题！")
                return
            try:
                await chat.restrict_member(user_id=user.id, permissions=ChatPermissions(can_send_messages=False))
            except BadRequest as exc:
                if "Not enough rights" in exc.message:
                    logger.warning("%s[%s] 权限不够", chat.title, chat.id)
                    await chat.send_message(
                        f"派蒙无法修改 {user.mention_html()} 的权限！请检查是否给派蒙授权管理了",
                        parse_mode=ParseMode.HTML,
                    )
                    return
                raise exc
            new_chat_members_message = await self.get_new_chat_members_message(user, context)
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
            if new_chat_members_message:
                reply_message = (
                    f"*欢迎来到「提瓦特」世界！* \n"
                    f"问题: {escape_markdown(question.text, version=2)} \n"
                    f"请在*{self.time_out}*秒内回答问题"
                )
            else:
                reply_message = (
                    f"*欢迎 {user.mention_markdown_v2()} 来到「提瓦特」世界！* \n"
                    f"问题: {escape_markdown(question.text, version=2)} \n"
                    f"请在*{self.time_out}*秒内回答问题"
                )
            logger.debug(
                "发送入群验证问题 %s[%s] \n给%s[%s] 在 %s[%s]",
                question.text,
                question.question_id,
                user.full_name,
                user.id,
                chat.title,
                chat.id,
            )
            try:
                if new_chat_members_message:
                    question_message = await new_chat_members_message.reply_markdown_v2(
                        reply_message, reply_markup=InlineKeyboardMarkup(buttons), allow_sending_without_reply=True
                    )
                else:
                    question_message = await chat.send_message(
                        reply_message,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )
            except BadRequest as exc:
                await chat.send_message("派蒙分心了一下，不小心忘记你了，你只能先退出群再重新进来吧。")
                raise exc
            context.job_queue.run_once(
                callback=self.kick_member_job,
                when=self.time_out,
                name=f"{chat.id}|{user.id}|auth_kick",
                chat_id=chat.id,
                user_id=user.id,
                job_kwargs={"replace_existing": True, "id": f"{chat.id}|{user.id}|auth_kick"},
            )
            if new_chat_members_message:
                context.job_queue.run_once(
                    callback=self.clean_message_job,
                    when=self.time_out,
                    data=new_chat_members_message.message_id,
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
            if PYROGRAM_AVAILABLE and self.mtp:
                try:
                    if new_chat_members_message:
                        if question_message.id - new_chat_members_message.id - 1:
                            message_ids = list(range(new_chat_members_message.id + 1, question_message.id))
                        else:
                            return
                    else:
                        message_ids = [question_message.id - 3, question_message.id]
                    messages_list = await self.mtp.get_messages(chat.id, message_ids=message_ids)
                    for find_message in messages_list:
                        if find_message.empty:
                            continue
                        if find_message.from_user and find_message.from_user.id == user.id:
                            await self.mtp.delete_messages(chat_id=chat.id, message_ids=find_message.id)
                            text: Optional[str] = None
                            if find_message.text and "@" in find_message.text:
                                text = f"{user.full_name} 由于加入群组后，在验证缝隙间发送了带有 @(Mention) 的消息，已被踢出群组，并加入了封禁列表。"
                            elif find_message.caption and "@" in find_message.caption:
                                text = f"{user.full_name} 由于加入群组后，在验证缝隙间发送了带有 @(Mention) 的消息，已被踢出群组，并加入了封禁列表。"
                            elif find_message.forward_from_chat:
                                text = f"{user.full_name} 由于加入群组后，在验证缝隙间发送了带有 Forward 的消息，已被踢出群组，并加入了封禁列表。"
                            if text is not None:
                                await context.bot.ban_chat_member(chat.id, user.id)
                                button = [[InlineKeyboardButton("解除封禁", callback_data=f"auth_admin|pass|{user.id}")]]
                                await question_message.edit_text(text, reply_markup=InlineKeyboardMarkup(button))
                                if schedule := context.job_queue.scheduler.get_job(f"{chat.id}|{user.id}|auth_kick"):
                                    schedule.remove()
                            logger.info(
                                "用户 %s[%s] 在群 %s[%s] 验证缝隙间发送消息 现已删除", user.full_name, user.id, chat.title, chat.id
                            )
                except BadRequest as exc:
                    logger.error("后验证处理中发生错误 %s", exc.message)
                    logger.exception(exc)
                except MTPFloodWait:
                    logger.warning("调用 mtp 触发洪水限制")
                except MTPBadRequest as exc:
                    logger.error("调用 mtp 请求错误")
                    logger.exception(exc)
