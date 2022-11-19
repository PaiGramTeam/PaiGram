import json
from functools import wraps
from typing import Callable, cast

from aiohttp import ClientConnectorError
from genshin import InvalidCookies, GenshinException, TooManyRequests, DataNotPublic
from httpx import ConnectTimeout
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, TimedOut, Forbidden
from telegram.ext import CallbackContext, ConversationHandler

from modules.apihelper.error import APIHelperException, ReturnCodeError, APIHelperTimedOut, ResponseException
from utils.error import UrlResourcesNotFoundError
from utils.log import logger


async def send_user_notification(update: Update, context: CallbackContext, text: str):
    if not isinstance(update, Update):
        logger.warning("错误的消息类型 %s", repr(update))
        return
    if update.inline_query is not None:  # 忽略 inline_query
        return
    if "重新绑定" in text:
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("点我重新绑定", url=f"https://t.me/{context.bot.username}?start=set_cookie")]]
        )
    elif "通过验证" in text:
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("点我通过验证", url=f"https://t.me/{context.bot.username}?start=verify_verification")]]
        )
    else:
        buttons = ReplyKeyboardRemove()
    user = update.effective_user
    message = update.effective_message
    chat = update.effective_chat
    if message is None:
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        logger.warning("错误的消息类型\n %s", json.dumps(update_str, indent=2, ensure_ascii=False))
        return
    logger.info("尝试通知用户 %s[%s] 在 %s[%s] 的错误信息[%s]", user.full_name, user.id, chat.full_name, chat.id, text)
    try:
        await message.reply_text(text, reply_markup=buttons, allow_sending_without_reply=True)
    except ConnectTimeout:
        logger.error("httpx 模块连接服务器 ConnectTimeout 发送 update_id[%s] 错误信息失败", update.update_id)
    except BadRequest as exc:
        logger.error("发送 update_id[%s] 错误信息失败 错误信息为 [%s]", update.update_id, exc.message)
    except Forbidden as exc:
        logger.error("发送 update_id[%s] 错误信息失败 错误信息为 [%s]", update.update_id, exc.message)
    except Exception as exc:
        logger.error("发送 update_id[%s] 错误信息失败 错误信息为 [%s]", update.update_id, repr(exc))
        logger.exception(exc)


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
        try:
            return await func(*args, **kwargs)
        except ClientConnectorError:
            logger.error("aiohttp 模块连接服务器 ClientConnectorError")
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ 请稍后再试")
            return ConversationHandler.END
        except ConnectTimeout:
            logger.error("httpx 模块连接服务器 ConnectTimeout")
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ 请稍后再试")
            return ConversationHandler.END
        except TimedOut:
            logger.error("python-telegram-bot 模块连接服务器 TimedOut")
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ 请稍后再试")
            return ConversationHandler.END
        except UrlResourcesNotFoundError as exc:
            logger.error("URL数据资源未找到")
            logger.exception(exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ 资源未找到 ~ ")
            return ConversationHandler.END
        except InvalidCookies as exc:
            if exc.retcode in (10001, -100):
                await send_user_notification(update, context, "出错了呜呜呜 ~ Cookie 无效，请尝试重新绑定")
            elif exc.retcode == 10103:
                await send_user_notification(update, context, "出错了呜呜呜 ~ Cookie 有效，但没有绑定到游戏帐户，请尝试重新绑定")
            else:
                logger.warning("Cookie错误")
                logger.exception(exc)
                await send_user_notification(update, context, f"出错了呜呜呜 ~ Cookie 无效 错误信息为 {exc.original} 请尝试重新绑定")
            return ConversationHandler.END
        except TooManyRequests as exc:
            logger.warning("查询次数太多（操作频繁） %s", exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ 当天查询次数已经超过30次，请次日再进行查询")
            return ConversationHandler.END
        except DataNotPublic:
            await send_user_notification(update, context, "出错了呜呜呜 ~ 查询的用户数据未公开")
            return ConversationHandler.END
        except GenshinException as exc:
            if exc.retcode == -130:
                await send_user_notification(update, context, "出错了呜呜呜 ~ 未设置默认角色，请尝试重新绑定")
            elif exc.retcode == 1034:
                await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器检测到该账号可能存在异常，请求被拒绝，请尝试通过验证")
            elif exc.retcode == -500001:
                await send_user_notification(update, context, "出错了呜呜呜 ~ 网络出小差了，请稍后重试~")
            elif exc.retcode == -1:
                await send_user_notification(update, context, "出错了呜呜呜 ~ 系统发生错误，请稍后重试~")
            elif exc.retcode == -10001:  # 参数异常 应该抛出错误
                raise exc
            else:
                logger.error("GenshinException")
                logger.exception(exc)
                await send_user_notification(
                    update, context, f"出错了呜呜呜 ~ 获取账号信息发生错误 错误信息为 {exc.original if exc.original else exc.retcode} ~ 请稍后再试"
                )
            return ConversationHandler.END
        except ReturnCodeError as exc:
            await send_user_notification(update, context, f"出错了呜呜呜 ~ API请求错误 错误信息为 {exc.message} ~ 请稍后再试")
            return ConversationHandler.END
        except APIHelperTimedOut:
            logger.warning("APIHelperException")
            await send_user_notification(update, context, "出错了呜呜呜 ~ API请求超时 ~ 请稍后再试")
        except ResponseException as exc:
            logger.error("APIHelperException [%s]%s", exc.code, exc.message)
            await send_user_notification(
                update, context, f"出错了呜呜呜 ~ API请求错误 错误信息为 {exc.message if exc.message else exc.code} ~ 请稍后再试"
            )
            return ConversationHandler.END
        except APIHelperException as exc:
            logger.error("APIHelperException")
            logger.exception(exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ API请求错误 ~ 请稍后再试")
            return ConversationHandler.END
        except BadRequest as exc:
            if "Replied message not found" in exc.message:
                telegram_warning(update, exc.message)
                await send_user_notification(update, context, "气死我了！怎么有人喜欢发一个命令就秒删了！")
                return ConversationHandler.END
            if "Message is not modified" in exc.message:
                telegram_warning(update, exc.message)
                return ConversationHandler.END
            logger.error("python-telegram-bot 请求错误")
            logger.exception(exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ telegram-bot-api请求错误 ~ 请稍后再试")
            return ConversationHandler.END
        except Forbidden as exc:
            logger.error("python-telegram-bot 返回 Forbidden")
            logger.exception(exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ telegram-bot-api请求错误 ~ 请稍后再试")
            return ConversationHandler.END

    return decorator
