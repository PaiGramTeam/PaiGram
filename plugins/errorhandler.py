import html
import traceback
from typing import Callable, Optional

import ujson
from aiohttp import ClientConnectorError
from genshin import InvalidCookies, GenshinException, TooManyRequests
from httpx import ConnectTimeout
from telegram import Update, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.error import BadRequest, TimedOut
from telegram.ext import CallbackContext, ConversationHandler

from config import config
from logger import Log

try:
    notice_chat_id = config.TELEGRAM["notice"]["ERROR"]["chat_id"]
except KeyError as error:
    Log.warning("错误通知Chat_id获取失败或未配置，BOT发生致命错误时不会收到通知 错误信息为\n", error)
    notice_chat_id = None


async def send_user_notification(update: Update, _: CallbackContext, text: str):
    effective_user = update.effective_user
    if update.callback_query is None:
        message = update.message
    else:
        message = update.callback_query.message
    chat = message.chat
    Log.info(f"尝试通知用户 {effective_user.full_name}[{effective_user.id}] "
             f"在 {chat.full_name}[{chat.id}]"
             f"的 错误信息[{text}]")
    try:
        await message.reply_text(text, reply_markup=ReplyKeyboardRemove(), allow_sending_without_reply=True)
    except BadRequest as exc:
        Log.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为 {str(exc)}")
    finally:
        pass


def conversation_error_handler(func: Callable) -> Callable:
    """
    Conversation的错误处理修饰器
    非常感谢 @Bibo-Joshi 提出的建议
    """

    async def decorator(*args, **kwargs):
        update: Optional[Update] = None
        context: Optional[CallbackContext] = None
        for arg in args:
            if isinstance(arg, Update):
                update = arg
            if isinstance(arg, CallbackContext):
                context = arg
        if update is None or context is None:
            return await func(*args, **kwargs)
        try:
            return await func(*args, **kwargs)
        except ClientConnectorError as exc:
            Log.error("服务器请求ConnectTimeout", exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ ")
            return ConversationHandler.END
        except ConnectTimeout as exc:
            Log.error("服务器请求ConnectTimeout", exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ ")
            return ConversationHandler.END
        except TimedOut as exc:
            Log.error("服务器请求ConnectTimeout", exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ ")
            return ConversationHandler.END
        except InvalidCookies as exc:
            Log.warning("Cookie错误", exc)
            await send_user_notification(update, context, "Cookies已经过期，请尝试重新绑定账户")
            return ConversationHandler.END
        except TooManyRequests as exc:
            Log.warning("查询次数太多（操作频繁）", exc)
            await send_user_notification(update, context, "当天查询次数已经超过30次，请次日再进行查询")
            return ConversationHandler.END
        except GenshinException as exc:
            Log.warning("GenshinException", exc)
            await send_user_notification(update, context,
                                         f"获取账号信息发生错误，错误信息为 {str(error)}，请检查Cookie或者账号是否正常")
            return ConversationHandler.END
        except BadRequest as exc:
            Log.warning("python-telegram-bot请求错误", exc)
            await send_user_notification(update, context, f"telegram-bot-api请求错误 错误信息为 {str(exc)}")
            return ConversationHandler.END

    return decorator


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
    text_1 = (
        f'<b>处理函数时发生异常</b> \n'
        f'Exception while handling an update \n'
        f'<pre>update = {html.escape(ujson.dumps(update_str, indent=2, ensure_ascii=False))}'
        '</pre>\n\n'
        f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n'
        f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n'
    )
    text_2 = (
        f'<pre>{html.escape(tb_string)}</pre>'
    )
    try:
        if 'make sure that only one bot instance is running' in tb_string:
            Log.error("其他机器人在运行，请停止！")
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
                    Log.error("处理函数时发生异常", exc_1)
    effective_user = update.effective_user
    try:
        message = update.message
        if message is not None:
            chat = message.chat
            Log.info(f"尝试通知用户 {effective_user.full_name}[{effective_user.id}] "
                     f"在 {chat.full_name}[{chat.id}]"
                     f"的 update_id[{update.update_id}] 错误信息")
            text = f"派蒙这边发生了点问题无法处理！\n" \
                   f"如果当前有对话请发送 /cancel 退出对话。\n" \
                   f"错误信息为 <code>{html.escape(str(context.error))}</code>"
            await context.bot.send_message(message.chat_id, text, reply_markup=ReplyKeyboardRemove(),
                                           parse_mode=ParseMode.HTML)
    except BadRequest as exc:
        Log.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为 {str(exc)}")
        pass
