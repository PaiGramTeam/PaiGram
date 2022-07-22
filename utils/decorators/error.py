from functools import wraps
from typing import Callable, Optional

import ujson
from aiohttp import ClientConnectorError
from genshin import InvalidCookies, GenshinException, TooManyRequests
from httpx import ConnectTimeout
from telegram import Update, ReplyKeyboardRemove, Message
from telegram.error import BadRequest, TimedOut, Forbidden
from telegram.ext import CallbackContext, ConversationHandler

from logger import Log


async def send_user_notification(update: Update, _: CallbackContext, text: str):
    effective_user = update.effective_user
    message: Optional[Message] = None
    if update.callback_query is not None:
        message = update.callback_query.message
    if update.message is not None:
        message = update.message
    if update.edited_message is not None:
        message = update.edited_message
    if message is None:
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        Log.warning("错误的消息类型\n" + ujson.dumps(update_str, indent=2, ensure_ascii=False))
        return
    chat = message.chat
    Log.info(f"尝试通知用户 {effective_user.full_name}[{effective_user.id}] "
             f"在 {chat.full_name}[{chat.id}]"
             f"的 错误信息[{text}]")
    try:
        await message.reply_text(text, reply_markup=ReplyKeyboardRemove(), allow_sending_without_reply=True)
    except BadRequest as exc:
        Log.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为 {str(exc)}")
    except Forbidden as exc:
        Log.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为 {str(exc)}")
    except BaseException as exc:
        Log.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为 {str(exc)}")
    finally:
        pass


def error_callable(func: Callable) -> Callable:
    """Plugins 错误处理修饰器

    非常感谢 @Bibo-Joshi 提出的建议
    """

    @wraps(func)
    async def decorator(*args, **kwargs):
        update: Optional[Update] = None
        context: Optional[CallbackContext] = None
        if len(args) == 3:
            # self update context
            _, update, context = args
        elif len(args) == 2:
            # update context
            update, context = args
        else:
            return await func(*args, **kwargs)
        try:
            return await func(*args, **kwargs)
        except ClientConnectorError:
            Log.error("aiohttp 模块连接服务器 ClientConnectorError")
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ ")
            return ConversationHandler.END
        except ConnectTimeout:
            Log.error("httpx 模块连接服务器 ConnectTimeout")
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ ")
            return ConversationHandler.END
        except TimedOut:
            Log.error("python-telegram-bot 模块连接服务器 TimedOut")
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ ")
            return ConversationHandler.END
        except InvalidCookies as exc:
            Log.warning("Cookie错误", exc)
            if "[10001]" in str(exc):
                await send_user_notification(update, context, "Cookies无效，请尝试重新绑定账户")
            elif "[-100]" in str(exc):
                await send_user_notification(update, context, "Cookies无效，请尝试重新绑定账户")
            elif "[10103]" in str(exc):
                await send_user_notification(update, context, "Cookie有效，但没有绑定到游戏帐户，请尝试重新绑定邮游戏账户")
            else:
                await send_user_notification(update, context, "Cookies无效，具体原因未知")
            return ConversationHandler.END
        except TooManyRequests as exc:
            Log.warning("查询次数太多（操作频繁）", exc)
            await send_user_notification(update, context, "当天查询次数已经超过30次，请次日再进行查询")
            return ConversationHandler.END
        except GenshinException as exc:
            if "[-130]" in str(exc):
                await send_user_notification(update, context, "未设置默认角色，请尝试重新绑定默认角色")
                return ConversationHandler.END
            Log.warning("GenshinException", exc)
            await send_user_notification(update, context,
                                         f"获取账号信息发生错误，错误信息为 {str(exc)}")
            return ConversationHandler.END
        except BadRequest as exc:
            Log.warning("python-telegram-bot 请求错误", exc)
            await send_user_notification(update, context, f"telegram-bot-api请求错误 错误信息为 {str(exc)}")
            return ConversationHandler.END
        except Forbidden as exc:
            Log.warning("python-telegram-bot返回 Forbidden", exc)
            await send_user_notification(update, context, "telegram-bot-api请求错误")
            return ConversationHandler.END

    return decorator
