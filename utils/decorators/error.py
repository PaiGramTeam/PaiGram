import json
from functools import wraps
from typing import Callable, cast

from aiohttp import ClientConnectorError
from genshin import InvalidCookies, GenshinException, TooManyRequests, DataNotPublic
from httpx import ConnectTimeout
from telegram import Update, ReplyKeyboardRemove
from telegram.error import BadRequest, TimedOut, Forbidden
from telegram.ext import CallbackContext, ConversationHandler

from modules.apihelper.error import APIHelperException, ReturnCodeError
from utils.error import UrlResourcesNotFoundError
from utils.log import logger


async def send_user_notification(update: Update, _: CallbackContext, text: str):
    effective_user = update.effective_user
    message = update.effective_message
    if message is None:
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        logger.warning("错误的消息类型\n" + json.dumps(update_str, indent=2, ensure_ascii=False))
        return
    chat = message.chat
    logger.info(f"尝试通知用户 {effective_user.full_name}[{effective_user.id}] "
                f"在 {chat.full_name}[{chat.id}]"
                f"的 错误信息[{text}]")
    try:
        await message.reply_text(text, reply_markup=ReplyKeyboardRemove(), allow_sending_without_reply=True)
    except BadRequest as exc:
        logger.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为")
        logger.exception(exc)
    except Forbidden as exc:
        logger.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为")
        logger.exception(exc)
    except BaseException as exc:
        logger.error(f"发送 update_id[{update.update_id}] 错误信息失败 错误信息为")
        logger.exception(exc)
    finally:
        pass


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
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ ")
            return ConversationHandler.END
        except ConnectTimeout:
            logger.error("httpx 模块连接服务器 ConnectTimeout")
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ ")
            return ConversationHandler.END
        except TimedOut:
            logger.error("python-telegram-bot 模块连接服务器 TimedOut")
            await send_user_notification(update, context, "出错了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ ")
            return ConversationHandler.END
        except UrlResourcesNotFoundError as exc:
            logger.error("URL数据资源未找到")
            logger.exception(exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ 资源未找到 ~ ")
            return ConversationHandler.END
        except InvalidCookies as exc:
            if exc.retcode in (10001, -100):
                await send_user_notification(update, context, "出错了呜呜呜 ~ Cookies无效，请尝试重新绑定账户")
            elif exc.retcode == 10103:
                await send_user_notification(update, context, "出错了呜呜呜 ~ Cookie有效，但没有绑定到游戏帐户，"
                                                              "请尝试重新绑定邮游戏账户")
            else:
                logger.warning("Cookie错误")
                logger.exception(exc)
                await send_user_notification(update, context, f"出错了呜呜呜 ~ Cookies无效 错误信息为 {exc.msg}")
            return ConversationHandler.END
        except TooManyRequests as exc:
            logger.warning("查询次数太多（操作频繁）", exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ 当天查询次数已经超过30次，请次日再进行查询")
            return ConversationHandler.END
        except DataNotPublic:
            await send_user_notification(update, context, "出错了呜呜呜 ~ 查询的用户数据未公开")
            return ConversationHandler.END
        except GenshinException as exc:
            if exc.retcode == -130:
                await send_user_notification(update, context, "出错了呜呜呜 ~ 未设置默认角色，请尝试重新绑定默认角色")
                return ConversationHandler.END
            logger.error("GenshinException")
            logger.exception(exc)
            await send_user_notification(update, context, f"出错了呜呜呜 ~ 获取账号信息发生错误 错误信息为 {exc.msg}")
            return ConversationHandler.END
        except ReturnCodeError as exc:
            await send_user_notification(update, context, f"出错了呜呜呜 ~ API请求错误 错误信息为 {exc.message}")
            return ConversationHandler.END
        except APIHelperException as exc:
            logger.error("APIHelperException")
            logger.exception(exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ API请求错误")
            return ConversationHandler.END
        except BadRequest as exc:
            logger.error("python-telegram-bot 请求错误")
            logger.exception(exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ telegram-bot-api请求错误")
            return ConversationHandler.END
        except Forbidden as exc:
            logger.error("python-telegram-bot返回 Forbidden")
            logger.exception(exc)
            await send_user_notification(update, context, "出错了呜呜呜 ~ telegram-bot-api请求错误")
            return ConversationHandler.END

    return decorator
