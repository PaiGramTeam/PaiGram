import os
import time
import traceback

import aiofiles
from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut
from telegram.ext import CallbackContext

from core.config import config
from core.plugin import Plugin, error_handler
from modules.errorpush import (
    PbClient,
    PbClientException,
    SentryClient,
    SentryClientException,
)
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib


class ErrorHandler(Plugin):
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

    @error_handler(block=False)  # pylint: disable=E1123, E1120
    async def error_handler(self, update: object, context: CallbackContext) -> None:
        """记录错误并发送消息通知开发人员。 logger the error and send a telegram message to notify the developer."""

        if isinstance(context.error, NetworkError):
            logger.error("Bot请求异常 %s", context.error.message)
            return
        if isinstance(context.error, TimedOut):
            logger.error("Bot请求超时 %s", context.error.message)
            return

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
        except (BadRequest, Forbidden) as exc:
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
                    f"尝试通知用户 {effective_user.full_name}[{effective_user.id}] "
                    f"在 {chat.full_name}[{chat.id}]"
                    f"的 update_id[{update.update_id}] 错误信息"
                )
                text = "出错了呜呜呜 ~ 派蒙这边发生了点问题无法处理！"
                await context.bot.send_message(
                    effective_message.chat_id, text, reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.HTML
                )
        except (BadRequest, Forbidden) as exc:
            logger.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为")
            logger.exception(exc)
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
