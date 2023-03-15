from datetime import datetime
from typing import Dict, Optional

import genshin
from arkowrapper import ArkoWrapper
from genshin import DataNotPublic, GenshinException, InvalidCookies, types
from genshin.models import GenshinAccount
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, TelegramObject, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.basemodel import RegionEnum
from core.plugin import Plugin, conversation, handler
from core.services.cookies.models import CookiesDataBase as Cookies, CookiesStatusEnum
from core.services.cookies.services import CookiesService
from core.services.players.models import PlayersDataBase as Player, PlayerInfoSQLModel
from core.services.players.services import PlayersService, PlayerInfoService
from modules.apihelper.client.components.authclient import AuthClient
from modules.apihelper.models.genshin.cookies import CookiesModel
from utils.log import logger

__all__ = ("AccountCookiesPlugin",)


class AccountIdNotFound(Exception):
    pass


class AccountCookiesPluginData(TelegramObject):
    player: Optional[Player] = None
    cookies_data_base: Optional[Cookies] = None
    region: RegionEnum = RegionEnum.NULL
    cookies: dict = {}
    account_id: int = 0
    # player_id: int = 0
    genshin_account: Optional[GenshinAccount] = None

    def reset(self):
        self.player = None
        self.cookies_data_base = None
        self.region = RegionEnum.NULL
        self.cookies = {}
        self.account_id = 0
        self.genshin_account = None


CHECK_SERVER, INPUT_COOKIES, COMMAND_RESULT = range(10100, 10103)


class AccountCookiesPlugin(Plugin.Conversation):
    """Cookie绑定"""

    def __init__(
        self,
        players_service: PlayersService = None,
        cookies_service: CookiesService = None,
        player_info_service: PlayerInfoService = None,
    ):
        self.cookies_service = cookies_service
        self.players_service = players_service
        self.player_info_service = player_info_service

    # noinspection SpellCheckingInspection
    @staticmethod
    def parse_cookie(cookie: Dict[str, str]) -> Dict[str, str]:
        cookies = {}

        v1_keys = ["ltoken", "ltuid", "account_id", "cookie_token", "stoken", "stuid", "login_uid", "login_ticket"]
        v2_keys = ["ltoken_v2", "ltmid_v2", "ltuid_v2", "account_mid_v2", "cookie_token_v2", "account_id_v2"]

        for k in v1_keys + v2_keys:
            cookies[k] = cookie.get(k)

        return {k: v for k, v in cookies.items() if v is not None}

    @conversation.entry_point
    @handler.command(command="setcookie", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="setcookies", filters=filters.ChatType.PRIVATE, block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 绑定账号命令请求", user.full_name, user.id)
        account_cookies_plugin_data: AccountCookiesPluginData = context.chat_data.get("account_cookies_plugin_data")
        if account_cookies_plugin_data is None:
            account_cookies_plugin_data = AccountCookiesPluginData()
            context.chat_data["account_cookies_plugin_data"] = account_cookies_plugin_data
        else:
            account_cookies_plugin_data.reset()

        text = f'你好 {user.mention_markdown_v2()} {escape_markdown("！请选择要绑定的服务器！或回复退出取消操作")}'
        reply_keyboard = [["米游社", "HoYoLab"], ["退出"]]
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return CHECK_SERVER

    @conversation.entry_point
    @handler.command("qlogin", filters=filters.ChatType.PRIVATE, block=False)
    async def qrcode_login(self, update: Update, context: CallbackContext):
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 绑定账号命令请求", user.full_name, user.id)
        account_cookies_plugin_data: AccountCookiesPluginData = context.chat_data.get("account_cookies_plugin_data")
        if account_cookies_plugin_data is None:
            account_cookies_plugin_data = AccountCookiesPluginData()
            context.chat_data["account_cookies_plugin_data"] = account_cookies_plugin_data
        else:
            account_cookies_plugin_data.reset()
        account_cookies_plugin_data.region = RegionEnum.HYPERION
        auth_client = AuthClient()
        url, ticket = await auth_client.create_qrcode_login()
        data = auth_client.generate_qrcode(url)
        text = f"你好 {user.mention_html()} ！该绑定方法仅支持国服，请在3分钟内使用米游社扫码并确认进行绑定。"
        await message.reply_photo(data, caption=text, parse_mode=ParseMode.HTML)
        if await auth_client.check_qrcode_login(ticket):
            account_cookies_plugin_data.cookies = auth_client.cookies.to_dict()
            return await self.check_cookies(update, context)
        await message.reply_markdown_v2("可能是验证码已过期或者你没有同意授权，请重新发送命令进行绑定。")
        return ConversationHandler.END

    @conversation.state(state=CHECK_SERVER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def check_server(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        account_cookies_plugin_data: AccountCookiesPluginData = context.chat_data.get("account_cookies_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "米游社":
            region = RegionEnum.HYPERION
            bbs_name = "米游社"
        elif message.text == "HoYoLab":
            bbs_name = "HoYoLab"
            region = RegionEnum.HOYOLAB
        else:
            await message.reply_text("选择错误，请重新选择")
            return CHECK_SERVER
        account_cookies_plugin_data.region = region
        await message.reply_text(f"请输入{bbs_name}的Cookies！或回复退出取消操作", reply_markup=ReplyKeyboardRemove())
        if bbs_name == "米游社":
            help_message = (
                "<b>关于如何获取Cookies</b>\n"
                "<b>现在因为网站HttpOnly策略无法通过脚本获取，因此操作只能在PC上运行。</b>\n\n"
                "PC：\n"
                "1、打开<a href='https://user.mihoyo.com/'>通行证</a>或<a href='https://www.miyoushe.com/ys/'>社区</a>并登录\n"
                "2、进入通行证按F12打开开发者工具\n"
                "3、将开发者工具切换至网络(Network)并点击过滤栏中的文档(Document)并刷新页面\n"
                "4、在请求列表中选择第一个并点击\n"
                "5、找到并复制请求标头(Request Headers)中的<b>Cookie</b>\n"
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
                f"1、<a href='https://www.hoyolab.com/home'>打开社区并登录</a>\n"
                "2、按F12打开开发者工具\n"
                "3、将开发者工具切换至控制台(Console)\n"
                "4、复制下方的代码，并将其粘贴在控制台中，按下回车\n"
                f"<pre><code class='javascript'>{javascript}</code></pre>\n"
                "Android：\n"
                f"1、<a href='https://www.hoyolab.com/home'>通过 Via 打开 {bbs_name} 并登录</a>\n"
                "2、复制下方的代码，并将其粘贴在地址栏中，点击右侧箭头\n"
                f"<code>{javascript_android}</code>\n"
                "iOS：\n"
                "1、在App Store上安装Web Inspector，并在iOS设置- Safari浏览器-扩展-允许这些扩展下找到Web Inspector-打开，允许所有网站\n"
                f"2、<a href='https://www.hoyolab.com/home'>通过 Safari 打开 {bbs_name} 并登录</a>\n"
                "3、点击地址栏左侧的大小按钮 - Web Inspector扩展 - Console - 点击下方文本框复制下方代码粘贴：\n"
                f"<pre><code class='javascript'>{javascript}</code></pre>\n"
                "4、点击Console下的Execute"
            )
        await message.reply_html(help_message, disable_web_page_preview=True)
        return INPUT_COOKIES

    @conversation.state(state=INPUT_COOKIES)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def input_cookies(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        account_cookies_plugin_data: AccountCookiesPluginData = context.chat_data.get("account_cookies_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            # cookie str to dict
            wrapped = (
                ArkoWrapper(message.text.split(";"))
                .filter(lambda x: x != "")
                .map(lambda x: x.strip())
                .map(lambda x: ((y := x.split("=", 1))[0], y[1]))
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
        account_cookies_plugin_data.cookies = cookies
        return await self.check_cookies(update, context)

    async def check_cookies(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        account_cookies_plugin_data: AccountCookiesPluginData = context.chat_data.get("account_cookies_plugin_data")
        cookies = CookiesModel(**account_cookies_plugin_data.cookies)
        if account_cookies_plugin_data.region == RegionEnum.HYPERION:
            client = genshin.Client(cookies=cookies.to_dict(), region=types.Region.CHINESE)
        elif account_cookies_plugin_data.region == RegionEnum.HOYOLAB:
            client = genshin.Client(cookies=cookies.to_dict(), region=types.Region.OVERSEAS)
        else:
            logger.error("用户 %s[%s] region 异常", user.full_name, user.id)
            await message.reply_text("数据错误", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if not cookies.check():
            await message.reply_text("检测到Cookie不完整，可能会出现问题。", reply_markup=ReplyKeyboardRemove())
        try:
            if client.cookie_manager.user_id is None and cookies.is_v2:
                logger.info("检测到用户 %s[%s] 使用 V2 Cookie 正在尝试获取 account_id", user.full_name, user.id)
                if client.region == types.Region.CHINESE:
                    account_info = await client.get_hoyolab_user()
                    account_id = account_info.hoyolab_id
                    account_cookies_plugin_data.account_id = account_id
                    cookies.set_v2_uid(account_id)
                    logger.success("获取用户 %s[%s] account_id[%s] 成功", user.full_name, user.id, account_id)
                else:
                    logger.warning("用户 %s[%s] region[%s] 也许是不正确的", user.full_name, user.id, client.region.name)
            else:
                account_cookies_plugin_data.account_id = client.cookie_manager.user_id
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
        except AccountIdNotFound:
            logger.info("用户 %s[%s] 无法获取账号ID", user.full_name, user.id)
            await message.reply_text("无法获取账号ID，请检查Cookie是否正常", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except (AttributeError, ValueError) as exc:
            logger.warning("用户 %s[%s] Cookies错误", user.full_name, user.id)
            logger.debug("用户 %s[%s] Cookies错误", user.full_name, user.id, exc_info=exc)
            await message.reply_text("Cookies错误，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if cookies.login_ticket is not None:
            try:
                if cookies.login_ticket is not None:
                    auth_client = AuthClient(cookies=cookies)
                    if await auth_client.get_stoken_by_login_ticket():
                        logger.success("用户 %s[%s] 绑定时获取 stoken 成功", user.full_name, user.id)
                        if await auth_client.get_cookie_token_by_stoken():
                            logger.success("用户 %s[%s] 绑定时获取 cookie_token 成功", user.full_name, user.id)
                            if await auth_client.get_ltoken_by_stoken():
                                logger.success("用户 %s[%s] 绑定时获取 ltoken 成功", user.full_name, user.id)
                                auth_client.cookies.remove_v2()
            except Exception as exc:  # pylint: disable=W0703
                logger.error("绑定时获取新Cookie失败 [%s]", (str(exc)))
            finally:
                cookies.login_ticket = None
                cookies.login_uid = None
        genshin_account: Optional[GenshinAccount] = None
        level: int = 0
        # todo : 多账号绑定
        for temp in genshin_accounts:
            if temp.level >= level:  # 获取账号等级最高的
                level = temp.level
                genshin_account = temp
        if genshin_account is None:
            await message.reply_text("未找到原神账号，请确认账号信息无误。")
            return ConversationHandler.END
        account_cookies_plugin_data.genshin_account = genshin_account
        player_info = await self.players_service.get(
            user.id, player_id=genshin_account.uid, region=account_cookies_plugin_data.region
        )
        account_cookies_plugin_data.player = player_info
        if player_info:
            cookies_database = await self.cookies_service.get(
                user.id, player_info.account_id, account_cookies_plugin_data.region
            )
            if cookies_database:
                account_cookies_plugin_data.cookies_data_base = cookies_database
                await message.reply_text("警告，你已经绑定Cookie，如果继续操作会覆盖当前Cookie。")
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("获取角色基础信息成功，请检查是否正确！")
        logger.info(
            "用户 %s[%s] 获取账号 %s[%s] 信息成功", user.full_name, user.id, genshin_account.nickname, genshin_account.uid
        )
        text = (
            f"*角色信息*\n"
            f"角色名称：{escape_markdown(genshin_account.nickname, version=2)}\n"
            f"角色等级：{genshin_account.level}\n"
            f"UID：`{genshin_account.uid}`\n"
            f"服务器名称：`{genshin_account.server_name}`\n"
        )
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        account_cookies_plugin_data.cookies = cookies.to_dict()
        return COMMAND_RESULT

    @conversation.state(state=COMMAND_RESULT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        account_cookies_plugin_data: AccountCookiesPluginData = context.chat_data.get("account_cookies_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "确认":
            player = account_cookies_plugin_data.player
            genshin_account = account_cookies_plugin_data.genshin_account
            if player:
                await self.players_service.update(player)
                cookies_data_base = account_cookies_plugin_data.cookies_data_base
                if cookies_data_base:
                    cookies_data_base.data = account_cookies_plugin_data.cookies
                    cookies_data_base.status = CookiesStatusEnum.STATUS_SUCCESS
                    await self.cookies_service.update(cookies_data_base)
                else:
                    cookies = Cookies(
                        user_id=user.id,
                        account_id=account_cookies_plugin_data.account_id,
                        data=account_cookies_plugin_data.cookies,
                        region=account_cookies_plugin_data.region,
                        is_share=True,  # todo 用户可以自行选择是否将Cookies加入公共池
                    )
                    await self.cookies_service.add(cookies)
                logger.success("用户 %s[%s] 更新Cookies", user.full_name, user.id)
            else:
                player = Player(
                    user_id=user.id,
                    account_id=account_cookies_plugin_data.account_id,
                    player_id=genshin_account.uid,
                    region=account_cookies_plugin_data.region,
                    is_chosen=True,  # todo 多账号
                )
                player_info = await self.player_info_service.get(player)
                if player_info is None:
                    player_info = PlayerInfoSQLModel(
                        user_id=player.user_id,
                        player_id=player.player_id,
                        nickname=genshin_account.nickname,
                        create_time=datetime.now(),
                        is_update=True,
                    )  # 不添加更新时间
                    await self.player_info_service.add(player_info)
                await self.players_service.add(player)
                cookies = Cookies(
                    user_id=user.id,
                    account_id=account_cookies_plugin_data.account_id,
                    data=account_cookies_plugin_data.cookies,
                    region=account_cookies_plugin_data.region,
                    is_share=True,  # todo 用户可以自行选择是否将Cookies加入公共池
                )
                await self.cookies_service.add(cookies)
                logger.info("用户 %s[%s] 绑定账号成功", user.full_name, user.id)
            await message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("回复错误，请重新输入")
        return COMMAND_RESULT
