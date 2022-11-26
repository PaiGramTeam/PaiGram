import contextlib
from http.cookies import SimpleCookie, CookieError
from typing import Optional, Dict

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


class GetAccountIdException(Exception):
    pass


CHECK_SERVER, CHECK_PHONE, CHECK_CAPTCHA, INPUT_COOKIES, COMMAND_RESULT = range(10100, 10105)


class SetUserCookies(Plugin.Conversation, BasePlugin.Conversation):
    """Cookie绑定"""

    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None):
        self.cookies_service = cookies_service
        self.user_service = user_service

    @staticmethod
    def de_cookie(cookie: SimpleCookie) -> Dict[str, str]:
        cookies = {}
        ltoken = cookie.get("ltoken")
        if ltoken:
            cookies["ltoken"] = ltoken.value
        ltuid = cookie.get("ltuid")
        login_uid = cookie.get("login_uid")
        if ltuid:
            cookies["ltuid"] = ltuid.value
            cookies["account_id"] = ltuid.value
        if login_uid:
            cookies["ltuid"] = login_uid.value
            cookies["account_id"] = ltuid.value
        cookie_token = cookie.get("cookie_token")
        cookie_token_v2 = cookie.get("cookie_token_v2")
        if cookie_token:
            cookies["cookie_token"] = cookie_token.value
        if cookie_token_v2:
            cookies["cookie_token"] = cookie_token_v2.value
        account_mid_v2 = cookie.get("account_mid_v2")
        if account_mid_v2:
            cookies["account_mid_v2"] = account_mid_v2.value
        cookie_token_v2 = cookie.get("cookie_token_v2")
        if cookie_token_v2:
            cookies["cookie_token_v2"] = cookie_token_v2.value
        ltoken_v2 = cookie.get("ltoken_v2")
        if ltoken_v2:
            cookies["ltoken_v2"] = ltoken_v2.value
        ltmid_v2 = cookie.get("ltmid_v2")
        if ltmid_v2:
            cookies["ltmid_v2"] = ltmid_v2.value
        login_ticket = cookie.get("login_ticket")
        if login_ticket:
            cookies["login_ticket"] = login_ticket.value
        return cookies

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
        if bbs_name == "米游社":
            help_message = (
                "<b>关于如何获取Cookies</b>\n"
                "<b>现在因为网站HttpOnly策略无法通过脚本获取，因此操作只能在PC上运行。</b>\n\n"
                "PC：\n"
                f"1、<a href='{bbs_url}'>打开 {bbs_name} 并登录</a>\n"
                "2、按F12打开开发者工具\n"
                "3、将开发者工具切换至网络(Network)并🎨 Update help message点击过滤栏中的文档(Document)并刷新页面\n"
                "4、在请求列表找到 <i>/ys</i> 并点击\n"
                "5、找到并复制请求标头(Request Headers)中的Cookie\n"
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
                f"<pre><code class='javascript'>{javascript}</code></pre>"
                "Android：\n"
                f"1、<a href='{bbs_url}'>通过 Via 打开 {bbs_name} 并登录</a>\n"
                "2、复制下方的代码，并将其粘贴在地址栏中，点击右侧箭头\n"
                f"<code>{javascript_android}</code>\n"
                "iOS：\n"
                "1、在App Store上安装Web Inspector，并在iOS设置- Safari浏览器-扩展-允许这些扩展下找到Web Inspector-打开，允许所有网站\n"
                f"2、<a href='{bbs_url}'>通过 Safari 打开 {bbs_name} 并登录</a>\n"
                "3、点击地址栏左侧的大小按钮 - Web Inspector扩展 - Console - 点击下方文本框复制下方代码粘贴："
                f"<pre><code class='javascript'>{javascript}</code></pre>"
                "4、点击Console下的Execute"
            )
        await message.reply_html(help_message, disable_web_page_preview=True)
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
        user = update.effective_user
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_user_command_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        str_cookies = message.text
        cookie = SimpleCookie()
        try:
            cookie.load(str_cookies)
        except CookieError:
            logger.info("用户 %s[%s] Cookies格式有误", user.full_name, user.id)
            await message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if len(cookie) == 0:
            logger.info("用户 %s[%s] Cookies格式有误", user.full_name, user.id)
            await message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            cookies = self.de_cookie(cookie)
        except (AttributeError, ValueError) as exc:
            logger.info("用户 %s[%s] Cookies解析出现错误", user.full_name, user.id)
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
            client = genshin.ChineseClient(cookies=cookies)
        elif add_user_command_data.region == RegionEnum.HOYOLAB:
            client = genshin.GenshinClient(cookies=cookies)
        else:
            logger.error("用户 %s[%s] region 异常", user.full_name, user.id)
            await message.reply_text("数据错误", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            if "account_mid_v2" in cookies:
                logger.info("检测到用户 %s[%s] 使用 V2 Cookie 正在尝试获取 account_id", user.full_name, user.id)
                account_id = await SignIn.get_v2_account_id(client)
                if account_id is None:
                    raise GetAccountIdException
                logger.success("获取用户 %s[%s] account_id[%s] 成功", user.full_name, user.id, account_id)
                add_user_command_data.cookies["account_id"] = account_id
            genshin_accounts = await client.genshin_accounts()
        except DataNotPublic:
            logger.info("用户 %s[%s] 账号疑似被注销", user.full_name, user.id)
            await message.reply_text("账号疑似被注销，请检查账号状态", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except InvalidCookies:
            logger.info("用户 %s[%s] Cookies已经过期", user.full_name, user.id)
            await message.reply_text("Cookies已经过期，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except GenshinException as exc:
            logger.info("用户 %s[%s] 获取账号信息发生错误 [%s]%s", user.full_name, user.id, exc.retcode, exc.original)
            await message.reply_text(
                f"获取账号信息发生错误，错误信息为 {exc.original}，请检查Cookie或者账号是否正常", reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        except GetAccountIdException:
            logger.info("用户 %s[%s] 获取账号ID发生错误", user.full_name, user.id)
            await message.reply_text("获取账号ID发生错误，请检查Cookie或者账号是否正常", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except (AttributeError, ValueError) as exc:
            logger.warning("用户 %s[%s] Cookies错误", user.full_name, user.id)
            logger.debug("Cookies错误", exc_info=exc)
            await message.reply_text("Cookies错误，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        with contextlib.suppress(Exception):
            if cookies.get("login_ticket"):
                sign_in_client = SignIn(cookie=add_user_command_data.cookies)
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
