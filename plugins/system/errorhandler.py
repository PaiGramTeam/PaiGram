import html
import json
import traceback

from telegram import Update, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext

from core.bot import bot
from core.plugin import error_handler, Plugin
from utils.log import logger

notice_chat_id = bot.config.error_notification_chat_id


class ErrorHandler(Plugin):

    @error_handler(block=False)
    async def error_handler(self, update: object, context: CallbackContext) -> None:
        """记录错误并发送消息通知开发人员。 logger the error and send a telegram message to notify the developer."""

        logger.error("处理函数时发生异常")
        logger.exception(context.error)

        if notice_chat_id is None:
            return

        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = ''.join(tb_list)

        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        text_1 = (
            f'<b>处理函数时发生异常</b> \n'
            f'Exception while handling an update \n'
            f'<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}'
            '</pre>\n\n'
            f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n'
            f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n'
        )
        text_2 = (
            f'<pre>{html.escape(tb_string)}</pre>'
        )
        try:
            if 'make sure that only one bot instance is running' in tb_string:
                logger.error("其他机器人在运行，请停止！")
                return
            await context.bot.send_message(notice_chat_id, text_1, parse_mode=ParseMode.HTML)
            await context.bot.send_message(notice_chat_id, text_2, parse_mode=ParseMode.HTML)
        except BadRequest as exc:
            if 'too long' in str(exc):
                text = (
                    f'<b>处理函数时发生异常，traceback太长导致无法发送，但已写入日志</b> \n'
                    f'<code>{html.escape(str(context.error))}</code>'
                )
                try:
                    await context.bot.send_message(notice_chat_id, text, parse_mode=ParseMode.HTML)
                except BadRequest:
                    text = (
                        '<b>处理函数时发生异常，traceback太长导致无法发送，但已写入日志</b> \n')
                    try:
                        await context.bot.send_message(notice_chat_id, text, parse_mode=ParseMode.HTML)
                    except BadRequest as exc_1:
                        logger.error("处理函数时发生异常", exc_1)
        effective_user = update.effective_user
        effective_message = update.effective_message
        try:
            if effective_message is not None:
                chat = effective_message.chat
                logger.info(f"尝试通知用户 {effective_user.full_name}[{effective_user.id}] "
                            f"在 {chat.full_name}[{chat.id}]"
                            f"的 update_id[{update.update_id}] 错误信息")
                text = f"出错了呜呜呜 ~ 派蒙这边发生了点问题无法处理！"
                await context.bot.send_message(effective_message.chat_id, text, reply_markup=ReplyKeyboardRemove(),
                                               parse_mode=ParseMode.HTML)
        except (BadRequest, Forbidden) as exc:
            logger.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为")
            logger.exception(exc)
