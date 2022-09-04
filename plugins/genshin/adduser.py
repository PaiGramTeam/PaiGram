from http.cookies import SimpleCookie, CookieError
from typing import Optional

import genshin
from genshin import InvalidCookies, GenshinException, DataNotPublic
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup, TelegramObject
from telegram.ext import CallbackContext, filters, ConversationHandler
from telegram.helpers import escape_markdown

from core.baseplugin import BasePlugin
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler, conversation
from core.user.error import UserNotFoundError
from core.user.models import User
from core.user.services import UserService
from modules.base import RegionEnum
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class AddUserCommandData(TelegramObject):
    user: Optional[User] = None
    region: RegionEnum = RegionEnum.HYPERION
    cookies: dict = {}
    game_uid: int = 0


CHECK_SERVER, CHECK_COOKIES, COMMAND_RESULT = range(10100, 10103)


class AddUser(Plugin.Conversation, BasePlugin.Conversation):
    """用户绑定"""

    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None):
        self.cookies_service = cookies_service
        self.user_service = user_service

    @conversation.entry_point
    @handler.command(command='adduser', filters=filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        logger.info(f"用户 {user.full_name}[{user.id}] 绑定账号命令请求")
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if add_user_command_data is None:
            cookies_command_data = AddUserCommandData()
            context.chat_data["add_user_command_data"] = cookies_command_data

        message = f'你好 {user.mention_markdown_v2()} {escape_markdown("！请选择要绑定的服务器！或回复退出取消操作")}'
        reply_keyboard = [['米游社', 'HoYoLab'], ["退出"]]
        await update.message.reply_markdown_v2(message,
                                               reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

        return CHECK_SERVER

    @conversation.state(state=CHECK_SERVER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_server(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        try:
            user_info = await self.user_service.get_user_by_id(user.id)
        except UserNotFoundError:
            user_info = None
        add_user_command_data.user = user_info
        if update.message.text == "退出":
            await update.message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif update.message.text == "米游社":
            add_user_command_data.region = RegionEnum.HYPERION
            bbs_url = "https://bbs.mihoyo.com/ys/"
            bbs_name = "米游社"
            if user_info is not None:
                await update.message.reply_text("警告，你已经绑定Cookie，如果继续操作会覆盖当前Cookie。")
        elif update.message.text == "HoYoLab":
            bbs_url = "https://www.hoyolab.com/home"
            bbs_name = "HoYoLab"
            add_user_command_data.region = RegionEnum.HOYOLAB
            if user_info is not None:
                await update.message.reply_text("警告，你已经绑定Cookie，如果继续操作会覆盖当前Cookie。")
        else:
            await update.message.reply_text("选择错误，请重新选择")
            return CHECK_SERVER
        await update.message.reply_text(f"请输入{bbs_name}的Cookies！或回复退出取消操作", reply_markup=ReplyKeyboardRemove())
        javascript = "javascript:(()=>{_=(n)=>{for(i in(r=document.cookie.split(';'))){var a=r[i].split('=');if(a[" \
                     "0].trim()==n)return a[1]}};c=_('account_id')||alert('无效的Cookie,请重新登录!');c&&confirm(" \
                     "'将Cookie复制到剪贴板?')&&copy(document.cookie)})(); "
        javascript_android = "javascript:(()=>{prompt('',document.cookie)})();"
        help_message = f"*关于如何获取Cookies*\n\n" \
                       f"PC：\n" \
                       f"[1、打开{bbs_name}并登录]({bbs_url})\n" \
                       f"2、按F12打开开发者工具\n" \
                       f"3、{escape_markdown('将开发者工具切换至控制台(Console)页签', version=2)}\n" \
                       f"4、复制下方的代码，并将其粘贴在控制台中，按下回车\n" \
                       f"`{escape_markdown(javascript, version=2, entity_type='code')}`\n\n" \
                       f"Android：\n" \
                       f"[1、通过 Via 浏览器打开{bbs_name}并登录]({bbs_url})\n" \
                       f"2、复制下方的代码，并将其粘贴在地址栏中，点击右侧箭头\n" \
                       f"`{escape_markdown(javascript_android, version=2, entity_type='code')}`"
        await update.message.reply_markdown_v2(help_message, disable_web_page_preview=True)
        return CHECK_COOKIES

    @conversation.state(state=CHECK_COOKIES)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_cookies(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if update.message.text == "退出":
            await update.message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        str_cookies = update.message.text
        cookie = SimpleCookie()
        try:
            cookie.load(str_cookies)
        except CookieError:
            await update.message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if len(cookie) == 0:
            await update.message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        cookies = {key: morsel.value for key, morsel in cookie.items()}
        if not cookies:
            await update.message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if add_user_command_data.region == RegionEnum.HYPERION:
            client = genshin.ChineseClient(cookies=cookies)
        elif add_user_command_data.region == RegionEnum.HOYOLAB:
            client = genshin.GenshinClient(cookies=cookies)
        else:
            await update.message.reply_text("数据错误", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            user_info = await client.get_record_card()
        except DataNotPublic:
            await update.message.reply_text("账号疑似被注销，请检查账号状态", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except InvalidCookies:
            await update.message.reply_text("Cookies已经过期，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except GenshinException as error:
            await update.message.reply_text(f"获取账号信息发生错误，错误信息为 {str(error)}，请检查Cookie或者账号是否正常",
                                            reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except (AttributeError, ValueError):
            await update.message.reply_text("Cookies错误，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        add_user_command_data.cookies = cookies
        add_user_command_data.game_uid = user_info.uid
        reply_keyboard = [['确认', '退出']]
        await update.message.reply_text("获取角色基础信息成功，请检查是否正确！")
        logger.info(f"用户 {user.full_name}[{user.id}] 获取账号 {user_info.nickname}[{user_info.uid}] 信息成功")
        message = f"*角色信息*\n" \
                  f"角色名称：{escape_markdown(user_info.nickname, version=2)}\n" \
                  f"角色等级：{user_info.level}\n" \
                  f"UID：`{user_info.uid}`\n" \
                  f"服务器名称：`{user_info.server_name}`\n"
        await update.message.reply_markdown_v2(
            message,
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return COMMAND_RESULT

    @conversation.state(state=COMMAND_RESULT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if update.message.text == "退出":
            await update.message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif update.message.text == "确认":
            if add_user_command_data.user is None:
                if add_user_command_data.region == RegionEnum.HYPERION:
                    user_db = User(user_id=user.id, yuanshen_uid=add_user_command_data.game_uid,
                                   region=add_user_command_data.region)
                elif add_user_command_data.region == RegionEnum.HOYOLAB:
                    user_db = User(user_id=user.id, genshin_uid=add_user_command_data.game_uid,
                                   region=add_user_command_data.region)
                else:
                    await update.message.reply_text("数据错误")
                    return ConversationHandler.END
                await self.user_service.add_user(user_db)
                await self.cookies_service.add_cookies(user.id, add_user_command_data.cookies,
                                                       add_user_command_data.region)
            else:
                user_db = add_user_command_data.user
                user_db.region = add_user_command_data.region
                if add_user_command_data.region == RegionEnum.HYPERION:
                    user_db.yuanshen_uid = add_user_command_data.game_uid
                elif add_user_command_data.region == RegionEnum.HOYOLAB:
                    user_db.genshin_uid = add_user_command_data.game_uid
                else:
                    await update.message.reply_text("数据错误")
                    return ConversationHandler.END
                await self.user_service.update_user(user_db)
                await self.cookies_service.update_cookies(user.id, add_user_command_data.cookies,
                                                          add_user_command_data.region)
            logger.info(f"用户 {user.full_name}[{user.id}] 绑定账号成功")
            await update.message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await update.message.reply_text("回复错误，请重新输入")
            return COMMAND_RESULT
