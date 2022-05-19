import html
import traceback
import ujson

from telegram import Update, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext

from logger import Log
from config import config

try:
    notice_chat_id = config.TELEGRAM["notice"]["ERROR"]["char_id"]
    admin_list = []
    for admin in config.ADMINISTRATORS:
        admin_list.append(admin["user_id"])
except KeyError as error:
    Log.warning("错误通知Chat_id获取失败或未配置，BOT发生致命错误时不会收到通知 错误信息为\n", error)
    notice_chat_id = None
    admin_list = []


async def error_handler(update: object, context: CallbackContext) -> None:
    """
    记录错误并发送消息通知开发人员。
    Log the error and send a telegram message to notify the developer.
    """
    Log.error(msg="处理函数时发生异常:", exc_info=context.error)

    if notice_chat_id is None:
        return

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message_1 = (
        f'<b>处理函数时发生异常</b> \n'
        f'Exception while handling an update \n'
        f'<pre>update = {html.escape(ujson.dumps(update_str, indent=2, ensure_ascii=False))}'
        '</pre>\n\n'
        f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n'
        f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n'
    )
    message_2 = (
        f'<pre>{html.escape(tb_string)}</pre>'
    )
    try:
        if 'make sure that only one bot instance is running' in tb_string:
            Log.error("其他机器人在运行，请停止！")
            return
        await context.bot.send_message(chat_id=notice_chat_id, text=message_1, parse_mode=ParseMode.HTML)
        await context.bot.send_message(chat_id=notice_chat_id, text=message_2, parse_mode=ParseMode.HTML)
    except BadRequest as exc:
        if 'too long' in str(exc):
            message = (
                f'<b>处理函数时发生异常，traceback太长导致无法发送，但已写入日志</b> \n'
                f'<code>{html.escape(str(context.error))}</code>'
            )
            try:
                await context.bot.send_message(chat_id=notice_chat_id, text=message, parse_mode=ParseMode.HTML)
            except BadRequest:
                message = (
                    f'<b>处理函数时发生异常，traceback太长导致无法发送，但已写入日志</b> \n')
                try:
                    await context.bot.send_message(chat_id=notice_chat_id, text=message, parse_mode=ParseMode.HTML)
                except BadRequest as exc:
                    Log.error("处理函数时发生异常 \n", exc)
    try:
        message = update.message
        user = update.effective_user
        if message is not None:
            text = "派蒙这边发生了点问题！如果有任务请尽量退出任务。"
            if user is not None:
                if user.id in admin_list:
                    error_test = str(context.error)
                    if len(error_test) <= 50:
                        text += f"\n错误信息为 {str(context.error)}"
            await context.bot.send_message(message.chat_id, text, reply_markup=ReplyKeyboardRemove())
    except BadRequest:
        pass
