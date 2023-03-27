import os
import time
import traceback
from typing import Optional

import aiofiles
from aiohttp import ClientError, ClientConnectorError
from genshin import DataNotPublic, GenshinException, InvalidCookies, TooManyRequests
from httpx import HTTPError, TimeoutException
from telegram import ReplyKeyboardRemove, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError, TimedOut, NetworkError
from telegram.ext import CallbackContext, ApplicationHandlerStop, filters
from telegram.helpers import create_deep_linked_url

from core.config import config
from core.plugin import Plugin, error_handler
from modules.apihelper.error import APIHelperException, APIHelperTimedOut, ResponseException, ReturnCodeError
from modules.errorpush import (
    PbClient,
    PbClientException,
    SentryClient,
    SentryClientException,
)
from utils.log import logger
from utils.patch.aiohttp import AioHttpTimeoutException

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib


class ErrorHandler(Plugin):
    ERROR_MSG_PREFIX = "出错了呜呜呜 ~ "
    SEND_MSG_ERROR_NOTICE = "发送 update_id[%s] 错误信息失败 错误信息为 [%s]"

    def __init__(self):
        self.notice_chat_id = config.error.notification_chat_id
        current_dir = os.getcwd()
        logs_dir = os.path.join(current_dir, "logs")
        if not os.path.exists(logs_dir):
            os.mkdir(logs_dir)
        self.report_dir = os.path.join(current_dir, "report")
        if not os.path.exists(self.report_dir):
            os.mkdir(self.report_dir)
        self.pb_client = PbClient(config.error.pb_url, config.error.pb_sunset, config.error.pb_max_lines)
        self.sentry = SentryClient(config.error.sentry_dsn)

    async def notice_user(self, update: object, context: CallbackContext, content: str):
        if not isinstance(update, Update):
            logger.warning("错误的消息类型 %s", repr(update))
            return None
        if update.inline_query is not None:  # 忽略 inline_query
            return None

        if "重新绑定" in content:
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("点我重新绑定", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            )
        elif "通过验证" in content:
            buttons = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "点我通过验证", url=create_deep_linked_url(context.bot.username, "verify_verification")
                        )
                    ]
                ]
            )
        else:
            buttons = ReplyKeyboardRemove()

        user = update.effective_user
        message = update.effective_message
        chat = update.effective_chat

        if chat.id == user.id:
            logger.info("尝试通知用户 %s[%s] 错误信息[%s]", user.full_name, user.id, content)
        else:
            logger.info("尝试通知用户 %s[%s] 在 %s[%s] 的错误信息[%s]", user.full_name, user.id, chat.title, chat.id, content)
        try:
            if update.callback_query:
                await update.callback_query.answer(content, show_alert=True)
            else:
                reply_text = await message.reply_text(content, reply_markup=buttons, allow_sending_without_reply=True)
                if filters.ChatType.GROUPS.filter(reply_text):
                    self.add_delete_message_job(reply_text, context=context)
                    self.add_delete_message_job(message, context=context)
        except TelegramError as exc:
            logger.error(self.SEND_MSG_ERROR_NOTICE, update.update_id, exc.message)
        except Exception as exc:
            logger.error(self.SEND_MSG_ERROR_NOTICE, update.update_id, repr(exc), exc_info=exc)

    def create_notice_task(self, update: object, context: CallbackContext, content: str):
        context.application.create_task(self.notice_user(update, context, content), update)

    @error_handler()
    async def process_genshin_exception(self, update: object, context: CallbackContext):
        if not isinstance(context.error, GenshinException) or not isinstance(update, Update):
            return
        exc = context.error
        notice: Optional[str] = None
        if isinstance(exc, TooManyRequests):
            notice = self.ERROR_MSG_PREFIX + "Cookie 无效，请尝试重新绑定"
        elif isinstance(exc, InvalidCookies):
            if exc.retcode in (10001, -100):
                notice = self.ERROR_MSG_PREFIX + "Cookie 无效，请尝试重新绑定"
            elif exc.retcode == 10103:
                notice = self.ERROR_MSG_PREFIX + "Cookie 有效，但没有绑定到游戏帐户，请尝试登录通行证，在账号管理里面选择账号游戏信息，将原神设置为默认角色。"
            else:
                logger.error("未知Cookie错误", exc_info=exc)
                notice = self.ERROR_MSG_PREFIX + f"Cookie 无效 错误信息为 {exc.original} 请尝试重新绑定"
        elif isinstance(exc, DataNotPublic):
            notice = self.ERROR_MSG_PREFIX + "查询的用户数据未公开"
        else:
            if exc.retcode == -130:
                notice = self.ERROR_MSG_PREFIX + "未设置默认角色，请尝试重新绑定"
            elif exc.retcode == 1034:
                notice = self.ERROR_MSG_PREFIX + "服务器检测到该账号可能存在异常，请求被拒绝，请尝试通过验证"
            elif exc.retcode == -500001:
                notice = self.ERROR_MSG_PREFIX + "网络出小差了，请稍后重试~"
            elif exc.retcode == -1:
                notice = self.ERROR_MSG_PREFIX + "系统发生错误，请稍后重试~"
            elif exc.retcode == -10001:  # 参数异常 不应该抛出异常 进入下一步处理
                pass
            else:
                logger.error("GenshinException", exc_info=exc)
                notice = (
                    self.ERROR_MSG_PREFIX + f"获取账号信息发生错误 错误信息为 {exc.original if exc.original else exc.retcode} ~ 请稍后再试"
                )
        if notice:
            self.create_notice_task(update, context, notice)
            raise ApplicationHandlerStop

    @error_handler()
    async def process_telegram_exception(self, update: object, context: CallbackContext):
        if not isinstance(context.error, TelegramError) or not isinstance(update, Update):
            return
        notice: Optional[str] = None
        if isinstance(context.error, TimedOut):
            # notice = self.ERROR_MSG_PREFIX + " 连接 telegram 服务器超时"
            logger.error("连接 telegram 服务器超时 [%s]", repr(context.error))
            raise ApplicationHandlerStop
        if isinstance(context.error, BadRequest):
            if "Replied message not found" in context.error.message:
                notice = "气死我了！怎么有人喜欢发一个命令就秒删了！"
            elif "Message is not modified" in context.error.message:
                logger.warning("编辑消息异常")
                raise ApplicationHandlerStop
            elif "Not enough rights" in context.error.message:
                notice = self.ERROR_MSG_PREFIX + "权限不足，请检查对应权限是否开启"
            elif "Wrong file identifier specified" in context.error.message:
                notice = self.ERROR_MSG_PREFIX + "文件标识符未找到 ~ 请稍后再试"
            else:
                logger.error("python-telegram-bot 请求错误", exc_info=context.error)
                notice = self.ERROR_MSG_PREFIX + "telegram-bot-api请求错误 ~ 请稍后再试"
        elif isinstance(context.error, Forbidden):
            logger.error("python-telegram-bot 返回 Forbidden")
            notice = self.ERROR_MSG_PREFIX + "telegram-bot-api请求错误 ~ 请稍后再试"
        if notice:
            self.create_notice_task(update, context, notice)
            raise ApplicationHandlerStop

    @error_handler()
    async def process_telegram_update_exception(self, update: object, context: CallbackContext):
        if update is None and isinstance(context.error, NetworkError):
            logger.error("python-telegram-bot NetworkError : %s", context.error.message)
            raise ApplicationHandlerStop

    @error_handler()
    async def process_apihelper_exception(self, update: object, context: CallbackContext):
        if not isinstance(context.error, APIHelperException) or not isinstance(update, Update):
            return
        exc = context.error
        notice: Optional[str] = None
        if isinstance(exc, APIHelperTimedOut):
            notice = self.ERROR_MSG_PREFIX + " 服务器熟啦 ~ 请稍后再试"
        elif isinstance(exc, ReturnCodeError):
            notice = self.ERROR_MSG_PREFIX + f"API请求错误 错误信息为 {exc.message if exc.message else exc.code} ~ 请稍后再试"
        elif isinstance(exc, ResponseException):
            notice = self.ERROR_MSG_PREFIX + f"API请求错误 错误信息为 {exc.message if exc.message else exc.code} ~ 请稍后再试"
        if notice:
            self.create_notice_task(update, context, notice)
            raise ApplicationHandlerStop

    @error_handler()
    async def process_httpx_exception(self, update: object, context: CallbackContext):
        if not isinstance(context.error, HTTPError) or not isinstance(update, Update):
            return
        exc = context.error
        notice: Optional[str] = None
        if isinstance(exc, TimeoutException):
            notice = self.ERROR_MSG_PREFIX + " 服务器熟啦 ~ 请稍后再试"
            logger.warning("Httpx exception[%s]", str(exc))
        if notice:
            self.create_notice_task(update, context, notice)
            raise ApplicationHandlerStop

    @error_handler()
    async def process_aiohttp_exception(self, update: object, context: CallbackContext):
        if not isinstance(context.error, ClientError) or not isinstance(update, Update):
            return
        exc = context.error
        notice: Optional[str] = None
        if isinstance(exc, AioHttpTimeoutException):
            notice = self.ERROR_MSG_PREFIX + " 服务器熟啦 ~ 请稍后再试"
        elif isinstance(exc, ClientConnectorError):
            notice = self.ERROR_MSG_PREFIX + " 连接服务器异常"
        if notice:
            self.create_notice_task(update, context, notice)
            raise ApplicationHandlerStop

    @error_handler(block=False)
    async def process_z_error(self, update: object, context: CallbackContext) -> None:
        # 必须 `process_` 加上 `z` 保证该函数最后一个注册
        """记录错误并发送消息通知开发人员。
        logger the error and send a telegram message to notify the developer."""

        logger.error("处理函数时发生异常")
        logger.exception(context.error, exc_info=(type(context.error), context.error, context.error.__traceback__))

        if not self.notice_chat_id:
            return

        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)

        update_str = update.to_dict() if isinstance(update, Update) else str(update)

        error_text = (
            f"-----Exception while handling an update-----\n"
            f"update = {jsonlib.dumps(update_str, indent=2, ensure_ascii=False)}\n"
            f"context.chat_data = {str(context.chat_data)}\n"
            f"context.user_data = {str(context.user_data)}\n"
            "\n"
            "-----Traceback info-----\n"
            f"{tb_string}"
        )
        file_name = f"error_{update.update_id if isinstance(update, Update) else int(time.time())}.txt"
        log_file = os.path.join(self.report_dir, file_name)
        try:
            async with aiofiles.open(log_file, mode="w+", encoding="utf-8") as f:
                await f.write(error_text)
        except Exception as exc:  # pylint: disable=W0703
            logger.error("保存日记失败")
            logger.exception(exc)
        try:
            if "make sure that only one bot instance is running" in tb_string:
                logger.error("其他机器人在运行，请停止！")
                return
            await context.bot.send_document(
                chat_id=self.notice_chat_id,
                document=open(log_file, "rb"),
                caption=f'Error: "{context.error.__class__.__name__}"',
            )
        except NetworkError as exc:
            logger.error("发送日记失败")
            logger.exception(exc)
        except FileNotFoundError:
            logger.error("发送日记失败 文件不存在")
        effective_user = update.effective_user
        effective_message = update.effective_message
        try:
            if effective_message is not None:
                chat = effective_message.chat
                logger.info(
                    "尝试通知用户 %s[%s] 在 %s[%s] 的 update_id[%s] 错误信息",
                    effective_user.full_name,
                    effective_user.id,
                    chat.full_name,
                    chat.id,
                    update.update_id,
                )
                text = "出错了呜呜呜 ~ 派蒙这边发生了点问题无法处理！"
                await context.bot.send_message(
                    effective_message.chat_id, text, reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.HTML
                )
        except NetworkError as exc:
            logger.error("发送 update_id[%s] 错误信息失败 错误信息为 %s", update.update_id, exc.message)
        if self.pb_client.enabled:
            logger.info("正在上传日记到 pb")
            try:
                pb_url = await self.pb_client.create_pb(error_text)
                if pb_url:
                    logger.success("上传日记到 pb 成功")
                    await context.bot.send_message(
                        chat_id=self.notice_chat_id,
                        text=f"错误信息已上传至 <a href='{pb_url}'>fars</a> 请查看",
                        parse_mode=ParseMode.HTML,
                    )
            except PbClientException as exc:
                logger.warning("上传错误信息至 fars 失败", exc_info=exc)
            except Exception as exc:
                logger.error("上传错误信息至 fars 失败")
                logger.exception(exc)
        if self.sentry.enabled:
            logger.info("正在上传日记到 sentry")
            try:
                self.sentry.report_error(update, (type(context.error), context.error, context.error.__traceback__))
                logger.success("上传日记到 sentry 成功")
            except SentryClientException as exc:
                logger.warning("上传错误信息至 sentry 失败", exc_info=exc)
            except Exception as exc:
                logger.error("上传错误信息至 sentry 失败")
                logger.exception(exc)
