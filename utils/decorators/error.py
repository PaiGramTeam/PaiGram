import json
from functools import wraps
from typing import Callable, cast, Optional

from aiohttp import ClientConnectorError
from genshin import InvalidCookies, GenshinException, TooManyRequests, DataNotPublic
from httpx import ConnectTimeout
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.error import BadRequest, TimedOut, Forbidden
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import create_deep_linked_url

from core.baseplugin import add_delete_message_job
from modules.apihelper.error import APIHelperException, ReturnCodeError, APIHelperTimedOut, ResponseException
from utils.error import UrlResourcesNotFoundError
from utils.log import logger


async def send_user_notification(update: Update, context: CallbackContext, text: str) -> Optional[Message]:
    if not isinstance(update, Update):
        logger.warning("错误的消息类型 %s", repr(update))
        return None
    if update.inline_query is not None:  # 忽略 inline_query
        return None
    if "重新绑定" in text:
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("点我重新绑定", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
        )
    elif "通过验证" in text:
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("点我通过验证", url=create_deep_linked_url(context.bot.username, "verify_verification"))]]
        )
    else:
        buttons = ReplyKeyboardRemove()
    user = update.effective_user
    message = update.effective_message
    chat = update.effective_chat
    if message is None:
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        logger.warning("错误的消息类型\n %s", json.dumps(update_str, indent=2, ensure_ascii=False))
        return None
    if chat.id == user.id:
        logger.info("尝试通知用户 %s[%s] 错误信息[%s]", user.full_name, user.id, chat.title, chat.id, text)
    else:
        logger.info("尝试通知用户 %s[%s] 在 %s[%s] 的错误信息[%s]", user.full_name, user.id, chat.title, chat.id, text)
    try:
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
            return None
        return await message.reply_text(text, reply_markup=buttons, allow_sending_without_reply=True)
    except ConnectTimeout:
        logger.error("httpx 模块连接服务器 ConnectTimeout 发送 update_id[%s] 错误信息失败", update.update_id)
    except BadRequest as exc:
        logger.error("发送 update_id[%s] 错误信息失败 错误信息为 [%s]", update.update_id, exc.message)
    except Forbidden as exc:
        logger.error("发送 update_id[%s] 错误信息失败 错误信息为 [%s]", update.update_id, exc.message)
    except Exception as exc:
        logger.error("发送 update_id[%s] 错误信息失败 错误信息为 [%s]", update.update_id, repr(exc))
        logger.exception(exc)
    return None


def telegram_warning(update: Update, text: str):
    user = update.effective_user
    message = update.effective_message
    chat = update.effective_chat
    msg = f"{text}\n user_id[{user.id}] chat_id[{chat.id}] message_id[{message.id}]"
    logger.warning(msg)


def error_callable(func: Callable) -> Callable:
    """Plugins 错误处理修饰器

    非常感谢 @Bibo-Joshi 提出的建议
    """

    @wraps(func)
    async def decorator(*args, **kwargs):
        if len(args) == 3:
            # self update context
            _, update, context = args
        elif len(args) == 2:
            # update context
            update, context = args
        else:
            return await func(*args, **kwargs)
        update = cast(Update, update)
        context = cast(CallbackContext, context)
        text: str = ""
        try:
            return await func(*args, **kwargs)
        except ClientConnectorError:
            logger.error("aiohttp 模块连接服务器 ClientConnectorError")
            text = "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ 请稍后再试"
        except ConnectTimeout:
            logger.error("httpx 模块连接服务器 ConnectTimeout")
            text = "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ 请稍后再试"
        except TimedOut:
            logger.error("python-telegram-bot 模块连接服务器 TimedOut")
            text = "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ 请稍后再试"
        except UrlResourcesNotFoundError as exc:
            logger.error("URL数据资源未找到")
            logger.exception(exc)
            text = "出错了呜呜呜 ~ 资源未找到 ~ "
        except InvalidCookies as exc:
            if exc.retcode in (10001, -100):
                text = "出错了呜呜呜 ~ Cookie 无效，请尝试重新绑定"
            elif exc.retcode == 10103:
                text = "出错了呜呜呜 ~ Cookie 有效，但没有绑定到游戏帐户，请尝试登录通行证，在账号管理里面选择账号游戏信息，将原神设置为默认角色。"
            else:
                logger.warning("Cookie错误")
                logger.exception(exc)
                text = f"出错了呜呜呜 ~ Cookie 无效 错误信息为 {exc.original} 请尝试重新绑定"
        except TooManyRequests as exc:
            logger.warning("查询次数太多（操作频繁） %s", exc)
            text = "出错了呜呜呜 ~ 当天查询次数已经超过30次，请次日再进行查询"
        except DataNotPublic:
            text = "出错了呜呜呜 ~ 查询的用户数据未公开"
        except GenshinException as exc:
            if exc.retcode == -130:
                text = "出错了呜呜呜 ~ 未设置默认角色，请尝试重新绑定"
            elif exc.retcode == 1034:
                text = "出错了呜呜呜 ~ 服务器检测到该账号可能存在异常，请求被拒绝，请尝试通过验证"
            elif exc.retcode == -500001:
                text = "出错了呜呜呜 ~ 网络出小差了，请稍后重试~"
            elif exc.retcode == -1:
                text = "出错了呜呜呜 ~ 系统发生错误，请稍后重试~"
            elif exc.retcode == -10001:  # 参数异常 应该抛出错误
                raise exc
            else:
                logger.error("GenshinException")
                logger.exception(exc)
                text = f"出错了呜呜呜 ~ 获取账号信息发生错误 错误信息为 {exc.original if exc.original else exc.retcode} ~ 请稍后再试"
        except ReturnCodeError as exc:
            text = f"出错了呜呜呜 ~ API请求错误 错误信息为 {exc.message} ~ 请稍后再试"
        except APIHelperTimedOut:
            logger.warning("APIHelperException")
            text = "出错了呜呜呜 ~ API请求超时 ~ 请稍后再试"
        except ResponseException as exc:
            logger.error("APIHelperException [%s]%s", exc.code, exc.message)
            text = f"出错了呜呜呜 ~ API请求错误 错误信息为 {exc.message if exc.message else exc.code} ~ 请稍后再试"
        except APIHelperException as exc:
            logger.error("APIHelperException")
            logger.exception(exc)
            text = "出错了呜呜呜 ~ API请求错误 ~ 请稍后再试"
        except BadRequest as exc:
            if "Replied message not found" in exc.message:
                telegram_warning(update, exc.message)
                text = "气死我了！怎么有人喜欢发一个命令就秒删了！"
            elif "Message is not modified" in exc.message:
                telegram_warning(update, exc.message)
            elif "Not enough rights" in exc.message:
                telegram_warning(update, exc.message)
                text = "出错了呜呜呜 ~ 权限不足，请检查对应权限是否开启"
            else:
                logger.error("python-telegram-bot 请求错误")
                logger.exception(exc)
                text = "出错了呜呜呜 ~ telegram-bot-api请求错误 ~ 请稍后再试"
        except Forbidden as exc:
            logger.error("python-telegram-bot 返回 Forbidden")
            logger.exception(exc)
            text = "出错了呜呜呜 ~ telegram-bot-api请求错误 ~ 请稍后再试"
        if text:
            notice_message = await send_user_notification(update, context, text)
            message = update.effective_message
            if message and not update.callback_query and filters.ChatType.GROUPS.filter(message):
                if notice_message:
                    add_delete_message_job(context, notice_message.chat_id, notice_message.message_id, 60)
                add_delete_message_job(context, message.chat_id, message.message_id, 60)
        else:
            user = update.effective_user
            chat = update.effective_chat
            logger.error("发送 %s[%s] 在 %s[%s] 的通知出现问题 通知文本不存在", user.full_name, user.id, chat.full_name, chat.id)
        return ConversationHandler.END

    return decorator
