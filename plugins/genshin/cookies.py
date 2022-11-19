import contextlib
from http.cookies import SimpleCookie, CookieError
from typing import Optional

import genshin
from genshin import InvalidCookies, GenshinException, DataNotPublic
from genshin.models import GenshinAccount
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup, TelegramObject
from telegram.ext import CallbackContext, filters, ConversationHandler
from telegram.helpers import escape_markdown

from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.cookies.models import Cookies
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler, conversation
from core.user.error import UserNotFoundError
from core.user.models import User
from core.user.services import UserService
from modules.apihelper.hyperion import SignIn
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger
from utils.models.base import RegionEnum


class AddUserCommandData(TelegramObject):
    user: Optional[User] = None
    cookies_database_data: Optional[Cookies] = None
    region: RegionEnum = RegionEnum.NULL
    cookies: dict = {}
    game_uid: int = 0
    phone: int = 0
    sign_in_client: Optional[SignIn] = None


CHECK_SERVER, CHECK_PHONE, CHECK_CAPTCHA, INPUT_COOKIES, COMMAND_RESULT = range(10100, 10105)


class SetUserCookies(Plugin.Conversation, BasePlugin.Conversation):
    """Cookie绑定"""

    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None):
        self.cookies_service = cookies_service
        self.user_service = user_service

    @conversation.entry_point
    @handler.command(command="setcookie", filters=filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] 绑定账号命令请求")
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if add_user_command_data is None:
            cookies_command_data = AddUserCommandData()
            context.chat_data["add_user_command_data"] = cookies_command_data

        text = f'你好 {user.mention_markdown_v2()} {escape_markdown("！请选择要绑定的服务器！或回复退出取消操作")}'
        reply_keyboard = [["米游社", "HoYoLab"], ["退出"]]
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return CHECK_SERVER

    @conversation.entry_point
    @handler.command(command="mlogin", filters=filters.ChatType.PRIVATE, block=True)
    @error_callable
    async def choose_method(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] 绑定账号命令请求")
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if add_user_command_data is None:
            cookies_command_data = AddUserCommandData()
            cookies_command_data.region = RegionEnum.HYPERION
            context.chat_data["add_user_command_data"] = cookies_command_data
        text = f'你好 {user.mention_markdown_v2()} {escape_markdown("！该绑定方法仅支持国服，请发送 11 位手机号码！或回复退出取消操作")}'
        await message.reply_markdown_v2(text)
        return CHECK_PHONE

    @conversation.state(state=CHECK_SERVER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_server(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif message.text == "米游社":
            region = RegionEnum.HYPERION
            bbs_url = "https://bbs.mihoyo.com/ys/"
            bbs_name = "米游社"
        elif message.text == "HoYoLab":
            bbs_url = "https://www.hoyolab.com/home"
            bbs_name = "HoYoLab"
            region = RegionEnum.HOYOLAB
        else:
            await message.reply_text("选择错误，请重新选择")
            return CHECK_SERVER
        try:
            user_info = await self.user_service.get_user_by_id(user.id)
        except UserNotFoundError:
            user_info = None
        if user_info is not None:
            try:
                cookies_database_data = await self.cookies_service.get_cookies(user.id, region)
                add_user_command_data.cookies_database_data = cookies_database_data
            except CookiesNotFoundError:
                await message.reply_text("你已经绑定UID，如果继续操作会覆盖当前UID。")
            else:
                await message.reply_text("警告，你已经绑定Cookie，如果继续操作会覆盖当前Cookie。")
        add_user_command_data.user = user_info
        add_user_command_data.region = region
        await message.reply_text(f"请输入{bbs_name}的Cookies！或回复退出取消操作", reply_markup=ReplyKeyboardRemove())
        javascript = (
            "javascript:(()=>{_=(n)=>{for(i in(r=document.cookie.split(';'))){var a=r[i].split('=');if(a["
            "0].trim()==n)return a[1]}};c=_('account_id')||alert('无效的Cookie,请重新登录!');c&&confirm("
            "'将Cookie复制到剪贴板?')&&copy(document.cookie)})(); "
        )
        javascript_android = "javascript:(()=>{prompt('',document.cookie)})();"
        help_message = (
            f"*关于如何获取Cookies*\n\n"
            f"PC：\n"
            f"[1、打开{bbs_name}并登录]({bbs_url})\n"
            f"2、按F12打开开发者工具\n"
            f"3、{escape_markdown('将开发者工具切换至控制台(Console)页签', version=2)}\n"
            f"4、复制下方的代码，并将其粘贴在控制台中，按下回车\n"
            f"`{escape_markdown(javascript, version=2, entity_type='code')}`\n\n"
            f"Android：\n"
            f"[1、通过 Via 浏览器打开{bbs_name}并登录]({bbs_url})\n"
            f"2、复制下方的代码，并将其粘贴在地址栏中，点击右侧箭头\n"
            f"`{escape_markdown(javascript_android, version=2, entity_type='code')}`"
        )
        await message.reply_markdown_v2(help_message, disable_web_page_preview=True)
        return INPUT_COOKIES

    @conversation.state(state=CHECK_PHONE)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_phone(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            if not message.text.startswith("1"):
                raise ValueError
            phone = int(message.text)
            if len(str(phone)) != 11:
                raise ValueError
        except ValueError:
            await message.reply_text("手机号码输入错误，请重新输入！或回复退出取消操作")
            return CHECK_PHONE
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        add_user_command_data.phone = phone
        await message.reply_text(
            "请打开 https://user.mihoyo.com/#/login/captcha ，输入手机号并获取验证码，" "然后将收到的验证码发送给我（请不要在网页上进行登录）"
        )
        return CHECK_CAPTCHA

    @conversation.state(state=CHECK_CAPTCHA)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_captcha(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            captcha = int(message.text)
            if len(str(captcha)) != 6:
                raise ValueError
        except ValueError:
            await message.reply_text("验证码输入错误，请重新输入！或回复退出取消操作")
            return CHECK_CAPTCHA
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if not add_user_command_data.sign_in_client:
            phone = add_user_command_data.phone
            client = SignIn(phone)
            try:
                success = await client.login(captcha)
                if not success:
                    await message.reply_text("登录失败：可能是验证码错误，注意不要在登录页面使用掉验证码，如果验证码已经使用，请重新获取验证码！")
                    return ConversationHandler.END
                await client.get_s_token()
            except Exception as exc:  # pylint: disable=W0703
                logger.error(f"用户 {user.full_name}[{user.id}] 登录失败 {repr(exc)}")
                await message.reply_text("登录失败：米游社返回了错误的数据，请稍后再试！")
                return ConversationHandler.END
            add_user_command_data.sign_in_client = client
            await message.reply_text(
                "请再次打开 https://user.mihoyo.com/#/login/captcha ，输入手机号并获取验证码（需要等待一分钟），" "然后将收到的验证码发送给我（请不要在网页上进行登录）"
            )
            return CHECK_CAPTCHA
        else:
            client = add_user_command_data.sign_in_client
            try:
                success = await client.get_token(captcha)
                if not success:
                    await message.reply_text("登录失败：可能是验证码错误，注意不要在登录页面使用掉验证码，如果验证码已经使用，请重新获取验证码！")
                    return ConversationHandler.END
            except Exception as exc:  # pylint: disable=W0703
                logger.error(f"用户 {user.full_name}[{user.id}] 登录失败 {repr(exc)}")
                await message.reply_text("登录失败：米游社返回了错误的数据，请稍后再试！")
                return ConversationHandler.END
            add_user_command_data.cookies = client.cookie
            return await self.check_cookies(update, context)

    @conversation.state(state=INPUT_COOKIES)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def input_cookies(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        str_cookies = message.text
        cookie = SimpleCookie()
        try:
            cookie.load(str_cookies)
        except CookieError:
            await message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if len(cookie) == 0:
            await message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        cookies = {key: morsel.value for key, morsel in cookie.items()}
        if not cookies:
            await message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        add_user_command_data.cookies = cookies
        return await self.check_cookies(update, context)

    @staticmethod
    async def check_cookies(update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        cookies = add_user_command_data.cookies
        if add_user_command_data.region == RegionEnum.HYPERION:
            client = genshin.ChineseClient(cookies=cookies)
        elif add_user_command_data.region == RegionEnum.HOYOLAB:
            client = genshin.GenshinClient(cookies=cookies)
        else:
            await message.reply_text("数据错误", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            genshin_accounts = await client.genshin_accounts()
        except DataNotPublic:
            await message.reply_text("账号疑似被注销，请检查账号状态", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except InvalidCookies:
            await message.reply_text("Cookies已经过期，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except GenshinException as exc:
            await message.reply_text(
                f"获取账号信息发生错误，错误信息为 {str(exc)}，请检查Cookie或者账号是否正常", reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        except (AttributeError, ValueError):
            await message.reply_text("Cookies错误，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        with contextlib.suppress(Exception):
            sign_in_client = SignIn(cookie=cookies)
            await sign_in_client.get_s_token()
            add_user_command_data.cookies = sign_in_client.cookie
            logger.info(f"用户 {user.full_name}[{user.id}] 绑定时获取 stoken 成功")
        user_info: Optional[GenshinAccount] = None
        level: int = 0
        # todo : 多账号绑定
        for genshin_account in genshin_accounts:
            if genshin_account.level >= level:  # 获取账号等级最高的
                level = genshin_account.level
                user_info = genshin_account
        if user_info is None:
            await message.reply_text("未找到原神账号，请确认账号信息无误。")
            return ConversationHandler.END
        add_user_command_data.game_uid = user_info.uid
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("获取角色基础信息成功，请检查是否正确！")
        logger.info(f"用户 {user.full_name}[{user.id}] 获取账号 {user_info.nickname}[{user_info.uid}] 信息成功")
        text = (
            f"*角色信息*\n"
            f"角色名称：{escape_markdown(user_info.nickname, version=2)}\n"
            f"角色等级：{user_info.level}\n"
            f"UID：`{user_info.uid}`\n"
            f"服务器名称：`{user_info.server_name}`\n"
        )
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return COMMAND_RESULT

    @conversation.state(state=COMMAND_RESULT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif message.text == "确认":
            if add_user_command_data.user is None:
                if add_user_command_data.region == RegionEnum.HYPERION:
                    user_db = User(
                        user_id=user.id,
                        yuanshen_uid=add_user_command_data.game_uid,
                        region=add_user_command_data.region,
                    )
                elif add_user_command_data.region == RegionEnum.HOYOLAB:
                    user_db = User(
                        user_id=user.id, genshin_uid=add_user_command_data.game_uid, region=add_user_command_data.region
                    )
                else:
                    await message.reply_text("数据错误")
                    return ConversationHandler.END
                await self.user_service.add_user(user_db)
            else:
                user_db = add_user_command_data.user
                user_db.region = add_user_command_data.region
                if add_user_command_data.region == RegionEnum.HYPERION:
                    user_db.yuanshen_uid = add_user_command_data.game_uid
                elif add_user_command_data.region == RegionEnum.HOYOLAB:
                    user_db.genshin_uid = add_user_command_data.game_uid
                else:
                    await message.reply_text("数据错误")
                    return ConversationHandler.END
                await self.user_service.update_user(user_db)
            if add_user_command_data.cookies_database_data is None:
                await self.cookies_service.add_cookies(
                    user.id, add_user_command_data.cookies, add_user_command_data.region
                )
            else:
                await self.cookies_service.update_cookies(
                    user.id, add_user_command_data.cookies, add_user_command_data.region
                )
            logger.info(f"用户 {user.full_name}[{user.id}] 绑定账号成功")
            await message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await message.reply_text("回复错误，请重新输入")
            return COMMAND_RESULT
