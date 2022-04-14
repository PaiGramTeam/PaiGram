from http.cookies import SimpleCookie
import ujson
import genshin
from genshin import InvalidCookies

from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from telegram.helpers import escape_markdown

from model.base import ServiceEnum
from plugins.base import BasePlugins
from service import BaseService
from service.base import UserInfoData


class CookiesCommandData:
    service = ServiceEnum.MIHOYO
    cookies: dict = {}
    game_uid: int = 0
    user_info: UserInfoData = UserInfoData()


class Cookies(BasePlugins):
    CHECK_SERVER, CHECK_COOKIES, COMMAND_RESULT = range(10100, 10103)

    def __init__(self, service: BaseService):
        super().__init__(service)

    async def command_start(self, update: Update, context: CallbackContext) -> int:
        cookies_command_data: CookiesCommandData = context.chat_data.get("cookies_command_data")
        if cookies_command_data is None:
            cookies_command_data = CookiesCommandData()
            context.chat_data["cookies_command_data"] = cookies_command_data
        user = update.effective_user
        message = f'你好 {user.mention_markdown_v2()} {escape_markdown("！请选择要绑定的服务器！或回复退出取消操作")}'
        # cookie = await self.repository.read_cookie(user.id)
        # if cookie != "":
        #    message = f'你好 {user.mention_markdown_v2()} ' \
        #              f'{escape_markdown("！你已经绑定Cookies！如果继续进行绑定会覆盖Cookie，可回复退出取消操作！")}'
        # await update.message.reply_markdown_v2(message, reply_markup=ReplyKeyboardRemove())
        reply_keyboard = [['miHoYo', 'HoYoLab'], ["退出"]]
        await update.message.reply_markdown_v2(message,
                                               reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

        return self.CHECK_SERVER

    async def check_server(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        cookies_command_data: CookiesCommandData = context.chat_data.get("cookies_command_data")
        user_info = await self.service.user_service_db.get_user_info(user.id)
        cookies_command_data.user_info = user_info
        if update.message.text == "退出":
            await update.message.reply_text("退出任务")
            return ConversationHandler.END
        elif update.message.text == "miHoYo":
            cookies_command_data.service = ServiceEnum.MIHOYO
            bbs_url = "https://bbs.mihoyo.com/ys/"
            bbs_name = "米游社"
            if len(user_info.mihoyo_cookie) > 1:
                await update.message.reply_text("警告，你已经绑定Cookie，如果继续操作会覆盖当前Cookie。")
        elif update.message.text == "HoYoLab":
            bbs_url = "https://www.hoyolab.com/home"
            bbs_name = "HoYoLab"
            cookies_command_data.service = ServiceEnum.HOYOLAB
            if len(user_info.hoyoverse_cookie) > 1:
                await update.message.reply_text("警告，你已经绑定Cookie，如果继续操作会覆盖当前Cookie。")
        else:
            await update.message.reply_text("选择错误，请重新选择")
            return self.CHECK_SERVER
        await update.message.reply_text(f"请输入{bbs_name}的Cookies！或回复退出取消操作", reply_markup=ReplyKeyboardRemove())
        javascript = "javascript:(()=>{_=(n)=>{for(i in(r=document.cookie.split(';'))){var a=r[i].split('=');if(a[" \
                     "0].trim()==n)return a[1]}};c=_('account_id')||alert('无效的Cookie,请重新登录!');c&&confirm(" \
                     "'将Cookie复制到剪贴板?')&&copy(document.cookie)})(); "
        help_message = f"*关于如何获取Cookies*\n" \
                       f"[1、打开{bbs_name}并登录]({bbs_url})\n" \
                       f"2、按F12打开开发者工具\n" \
                       f"3、{escape_markdown('将开发者工具切换至控制台(Console)页签', version=2)}\n" \
                       f"4、复制下方的代码，并将其粘贴在控制台中，按下回车\n" \
                       f"`{escape_markdown(javascript, version=2, entity_type='code')}`"
        await update.message.reply_markdown_v2(help_message, disable_web_page_preview=True)
        return self.CHECK_COOKIES

    async def check_cookies(self, update: Update, context: CallbackContext) -> int:
        cookies_command_data: CookiesCommandData = context.chat_data.get("cookies_command_data")
        if update.message.text == "退出":
            await update.message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        str_cookies = update.message.text
        cookie = SimpleCookie()
        cookie.load(str_cookies)
        if len(cookie) == 0:
            await update.message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        cookies = {}
        for key, morsel in cookie.items():
            cookies[key] = morsel.value
        if len(cookies) == 0:
            await update.message.reply_text("Cookies格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if cookies_command_data.service == ServiceEnum.MIHOYO:
            client = genshin.ChineseClient(cookies=cookies)
        elif cookies_command_data.service == ServiceEnum.HOYOLAB:
            client = genshin.GenshinClient(cookies=cookies)
        else:
            await update.message.reply_text("数据错误", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            user_info = await client.get_record_card()
        except InvalidCookies:
            await update.message.reply_text("Cookies已经过期，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except AttributeError:
            await update.message.reply_text("Cookies错误，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await client.close()
        cookies_command_data.cookies = cookies
        cookies_command_data.game_uid = user_info.uid
        reply_keyboard = [['确认', '退出']]
        await update.message.reply_text("获取角色基础信息成功，请检查是否正确！")
        message = f"*角色信息*\n" \
                  f"角色名称：{user_info.nickname}\n" \
                  f"角色等级：{user_info.level}\n" \
                  f"UID：`{user_info.uid}`\n" \
                  f"服务器名称：`{user_info.server_name}`\n"
        await update.message.reply_markdown_v2(message,
                                               reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.COMMAND_RESULT

    async def command_result(self, update: Update, context: CallbackContext) -> int:
        cookies_command_data: CookiesCommandData = context.chat_data.get("cookies_command_data")
        if update.message.text == "退出":
            await update.message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif update.message.text == "确认":
            user = update.effective_user
            data = ujson.dumps(cookies_command_data.cookies)
            user_info = cookies_command_data.user_info
            service = ServiceEnum.NULL.value
            if cookies_command_data.service == ServiceEnum.MIHOYO:
                user_info.mihoyo_game_uid = cookies_command_data.game_uid
                service = ServiceEnum.MIHOYO.value
            elif cookies_command_data.service == ServiceEnum.HOYOLAB:
                user_info.hoyoverse_game_uid = cookies_command_data.game_uid
                service = ServiceEnum.MIHOYO.value
            await self.service.user_service_db.set_user_info(user.id, user_info.mihoyo_game_uid,
                                                             user_info.hoyoverse_game_uid,
                                                             service)
            await self.service.user_service_db.set_cookie(user.id, data, cookies_command_data.service)
            await update.message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await update.message.reply_text("回复错误，请重新输入")
            return self.COMMAND_RESULT
