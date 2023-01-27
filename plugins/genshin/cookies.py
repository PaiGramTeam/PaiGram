import contextlib
from typing import Dict, Optional

import genshin
from arkowrapper import ArkoWrapper
from genshin import DataNotPublic, GenshinException, InvalidCookies, types
from genshin.models import GenshinAccount
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, TelegramObject, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.cookies.models import Cookies
from core.cookies.services import CookiesService
from core.plugin import Plugin, conversation, handler
from core.user.error import UserNotFoundError
from core.user.models import User
from core.user.services import UserService
from modules.apihelper.client.components.signin import SignIn
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger
from utils.models.base import RegionEnum


class AddUserCommandData(TelegramObject):
    user: Optional[User] = None
    region: RegionEnum = RegionEnum.NULL
    cookies: dict = {}
    game_uid: int = 0
    phone: int = 0
    sign_in_client: Optional[SignIn] = None


CHECK_SERVER, INPUT_COOKIES, COMMAND_RESULT = range(10100, 10103)


class SetUserCookies(Plugin.Conversation, BasePlugin.Conversation):
    """Cookie绑定"""

    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None):
        self.cookies_service = cookies_service
        self.user_service = user_service

    # noinspection SpellCheckingInspection
    @staticmethod
    def parse_cookie(cookie: Dict[str, str]) -> Dict[str, str]:
        cookies = {}

        v1_keys = ["ltoken", "ltuid", "login_uid", "cookie_token"]
        v2_keys = ["ltoken_v2", "ltmid_v2", "account_mid_v2", "cookie_token_v2", "login_ticket", "stoken"]

        cookie_is_v1 = None

        for k in v1_keys + v2_keys:
            v = cookie.get(k)
            if v is not None and cookie_is_v1 is None:
                cookie_is_v1 = k not in v2_keys
            cookies[k] = cookie.get(k)

        if cookie_is_v1:
            cookies["account_id"] = cookies["ltuid"]

        return {k: v for k, v in cookies.items() if v is not None}

    @conversation.entry_point
    @handler.command(command="setcookie", filters=filters.ChatType.PRIVATE, block=True)
    @handler.command(command="setcookies", filters=filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 绑定账号命令请求", user.full_name, user.id)
        cookies_command_data = AddUserCommandData()
        context.chat_data["add_user_command_data"] = cookies_command_data

        text = f'你好 {user.mention_markdown_v2()} {escape_markdown("！请选择要绑定的服务器！或回复退出取消操作")}'
        reply_keyboard = [["米游社", "HoYoLab"], ["退出"]]
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return CHECK_SERVER

    @conversation.entry_point
    @handler.command("qlogin", filters=filters.ChatType.PRIVATE, block=True)
    @error_callable
    async def qrcode_login(self, update: Update, context: CallbackContext):
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 绑定账号命令请求", user.full_name, user.id)
        add_user_command_data = AddUserCommandData()
        context.chat_data["add_user_command_data"] = add_user_command_data
        add_user_command_data.region = RegionEnum.HYPERION
        try:
            user_info = await self.user_service.get_user_by_id(user.id)
        except UserNotFoundError:
            user_info = None
        if user_info is not None:
            try:
                await self.cookies_service.get_cookies(user.id, RegionEnum.HYPERION)
            except CookiesNotFoundError:
                await message.reply_text("你已经绑定UID，如果继续操作会覆盖当前UID。")
            else:
                await message.reply_text("警告，你已经绑定Cookie，如果继续操作会覆盖当前Cookie。")
        add_user_command_data.user = user_info
        sign_in_client = SignIn()
        url = await sign_in_client.create_login_data()
        data = sign_in_client.generate_qrcode(url)
        text = f"你好 {user.mention_html()} ！该绑定方法仅支持国服，请在3分钟内使用米游社扫码并确认进行绑定。"
        await message.reply_photo(data, caption=text, parse_mode=ParseMode.HTML)
        if await sign_in_client.check_login():
            add_user_command_data.cookies = sign_in_client.cookie
            return await self.check_cookies(update, context)
        else:
            await message.reply_markdown_v2("可能是验证码已过期或者你没有同意授权，请重新发送命令进行绑定。")
            return ConversationHandler.END

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
            bbs_url = "https://user.mihoyo.com/"
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
                await self.cookies_service.get_cookies(user.id, region)
            except CookiesNotFoundError:
                await message.reply_text("你已经绑定UID，如果继续操作会覆盖当前UID。")
            else:
                await message.reply_text("警告，你已经绑定Cookie，如果继续操作会覆盖当前Cookie。")
        add_user_command_data.user = user_info
        add_user_command_data.region = region
        await message.reply_text(f"请输入{bbs_name}的Cookies！或回复退出取消操作", reply_markup=ReplyKeyboardRemove())
        if bbs_name == "米游社":
            help_message = (
                "<b>关于如何获取Cookies</b>\n"
                "<b>现在因为网站HttpOnly策略无法通过脚本获取，因此操作只能在PC上运行。</b>\n\n"
                "PC：\n"
                "1、<a href='https://www.miyoushe.com/ys/'>打开米游社并登录</a>\n"
                "2、<a href='https://user.mihoyo.com/'>打开通行证并登录</a>\n"
                "3、登录完成后刷新米游社和通行证网页\n"
                "4、进入通行证按F12打开开发者工具\n"
                "5、将开发者工具切换至网络(Network)并点击过滤栏中的文档(Document)并刷新页面\n"
                "6、在请求列表中选择第一个并点击\n"
                "7、找到并复制请求标头(Request Headers)中的<b>Cookie</b>\n"
                "<u>如发现没有请求标头(Request Headers)大概因为缓存的存在需要你点击禁用缓存(Disable Cache)再次刷新页面</u>"
            )
        else:
            javascript = (
                "javascript:(()=>{_=(n)=>{for(i in(r=document.cookie.split(';'))){var a=r[i].split('=');if(a["
                "0].trim()==n)return a[1]}};c=_('account_id')||alert('无效的Cookie,请重新登录!');c&&confirm("
                "'将Cookie复制到剪贴板?')&&copy(document.cookie)})(); "
            )
            javascript_android = "javascript:(()=>{prompt('',document.cookie)})();"
            help_message = (
                f"<b>关于如何获取Cookies</b>\n\n"
                f"PC：\n"
                f"1、<a href='{bbs_url}'>打开 {bbs_name} 并登录</a>\n"
                "2、按F12打开开发者工具\n"
                "3、将开发者工具切换至控制台(Console)\n"
                "4、复制下方的代码，并将其粘贴在控制台中，按下回车\n"
                f"<pre><code class='javascript'>{javascript}</code></pre>\n"
                "Android：\n"
                f"1、<a href='{bbs_url}'>通过 Via 打开 {bbs_name} 并登录</a>\n"
                "2、复制下方的代码，并将其粘贴在地址栏中，点击右侧箭头\n"
                f"<code>{javascript_android}</code>\n"
                "iOS：\n"
                "1、在App Store上安装Web Inspector，并在iOS设置- Safari浏览器-扩展-允许这些扩展下找到Web Inspector-打开，允许所有网站\n"
                f"2、<a href='{bbs_url}'>通过 Safari 打开 {bbs_name} 并登录</a>\n"
                "3、点击地址栏左侧的大小按钮 - Web Inspector扩展 - Console - 点击下方文本框复制下方代码粘贴：\n"
                f"<pre><code class='javascript'>{javascript}</code></pre>\n"
                "4、点击Console下的Execute"
            )
        await message.reply_html(help_message, disable_web_page_preview=True)
        return INPUT_COOKIES

    @conversation.state(state=INPUT_COOKIES)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def input_cookies(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            # cookie str to dict
            wrapped = (
                ArkoWrapper(message.text.split(";"))
                .filter(lambda x: x != "")
                .map(lambda x: x.strip())
                .map(lambda x: ((y := x.split("="))[0], y[1]))
            )
            cookie = {x[0]: x[1] for x in wrapped}
            cookies = self.parse_cookie(cookie)
        except (AttributeError, ValueError, IndexError) as exc:
            logger.info("用户 %s[%s] Cookies解析出现错误\ntext:%s", user.full_name, user.id, message.text)
            logger.debug("解析Cookies出现错误", exc_info=exc)
            await message.reply_text("解析Cookies出现错误，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if not cookies:
            logger.info("用户 %s[%s] Cookies格式有误", user.full_name, user.id)
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
            client = genshin.Client(cookies=cookies, region=types.Region.CHINESE)
        elif add_user_command_data.region == RegionEnum.HOYOLAB:
            client = genshin.Client(cookies=cookies, region=types.Region.OVERSEAS)
        else:
            logger.error("用户 %s[%s] region 异常", user.full_name, user.id)
            await message.reply_text("数据错误", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            if "account_mid_v2" in cookies:
                logger.info("检测到用户 %s[%s] 使用 V2 Cookie 正在尝试获取 account_id", user.full_name, user.id)
                if client.region == types.Region.CHINESE:
                    account_info = await client.get_hoyolab_user()
                    account_id = account_info.hoyolab_id
                    add_user_command_data.cookies["account_id"] = str(account_id)
                    logger.success("获取用户 %s[%s] account_id[%s] 成功", user.full_name, user.id, account_id)
                else:
                    logger.warning("用户 %s[%s] region[%s] 也许是不正确的", user.full_name, user.id, client.region.name)
            genshin_accounts = await client.genshin_accounts()
        except DataNotPublic:
            logger.info("用户 %s[%s] 账号疑似被注销", user.full_name, user.id)
            await message.reply_text("账号疑似被注销，请检查账号状态", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except InvalidCookies:
            logger.info("用户 %s[%s] Cookies已经过期", user.full_name, user.id)
            await message.reply_text(
                "获取账号信息失败，返回Cookies已经过期，请尝试在无痕浏览器中登录获取Cookies。", reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        except GenshinException as exc:
            logger.info("用户 %s[%s] 获取账号信息发生错误 [%s]%s", user.full_name, user.id, exc.retcode, exc.original)
            await message.reply_text(
                f"获取账号信息发生错误，错误信息为 {exc.original}，请检查Cookie或者账号是否正常", reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        except (AttributeError, ValueError) as exc:
            logger.warning("用户 %s[%s] Cookies错误", user.full_name, user.id)
            logger.debug("用户 %s[%s] Cookies错误", user.full_name, user.id, exc_info=exc)
            await message.reply_text("Cookies错误，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        with contextlib.suppress(Exception):
            if cookies.get("login_ticket"):
                sign_in_client = SignIn(cookie=add_user_command_data.cookies)
                await sign_in_client.get_s_token()
                add_user_command_data.cookies = sign_in_client.cookie
                logger.info("用户 %s[%s] 绑定时获取 stoken 成功", user.full_name, user.id)
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
        logger.info("用户 %s[%s] 获取账号 %s[%s] 信息成功", user.full_name, user.id, user_info.nickname, user_info.uid)
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
            await self.cookies_service.add_or_update_cookies(
                user.id, add_user_command_data.cookies, add_user_command_data.region
            )
            logger.info("用户 %s[%s] 绑定账号成功", user.full_name, user.id)
            await message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await message.reply_text("回复错误，请重新输入")
            return COMMAND_RESULT
