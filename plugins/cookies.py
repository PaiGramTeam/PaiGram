from http.cookies import SimpleCookie

import genshin
import ujson
from genshin import InvalidCookies, GenshinException, DataNotPublic
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters, ConversationHandler
from telegram.helpers import escape_markdown

from logger import Log
from model.base import ServiceEnum
from plugins.base import BasePlugins
from plugins.errorhandler import conversation_error_handler
from service import BaseService
from service.base import UserInfoData


class CookiesCommandData:
    service = ServiceEnum.MIHOYOBBS
    cookies: dict = {}
    game_uid: int = 0
    user_info: UserInfoData = UserInfoData()


class Cookies(BasePlugins):
    CHECK_SERVER, CHECK_COOKIES, COMMAND_RESULT = range(10100, 10103)

    def __init__(self, service: BaseService):
        super().__init__(service)

    @staticmethod
    def create_conversation_handler(service: BaseService):
        cookies = Cookies(service)
        cookies_handler = ConversationHandler(
            entry_points=[CommandHandler('adduser', cookies.command_start, filters.ChatType.PRIVATE, block=True),
                          MessageHandler(filters.Regex(r"^绑定账号(.*)") & filters.ChatType.PRIVATE,
                                         cookies.command_start, block=True)],
            states={
                cookies.CHECK_SERVER: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                      cookies.check_server, block=True)],
                cookies.CHECK_COOKIES: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                       cookies.check_cookies, block=True)],
                cookies.COMMAND_RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                        cookies.command_result, block=True)],
            },
            fallbacks=[CommandHandler('cancel', cookies.cancel, block=True)],
        )
        return cookies_handler

    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        Log.info(f"用户 {user.full_name}[{user.id}] 绑定账号命令请求")
        cookies_command_data: CookiesCommandData = context.chat_data.get("cookies_command_data")
        if cookies_command_data is None:
            cookies_command_data = CookiesCommandData()
            context.chat_data["cookies_command_data"] = cookies_command_data

        message = f'你好 {user.mention_markdown_v2()} {escape_markdown("！请选择要绑定的服务器！或回复退出取消操作")}'
        reply_keyboard = [['米游社', 'HoYoLab'], ["退出"]]
        await update.message.reply_markdown_v2(message,
                                               reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

        return self.CHECK_SERVER

    async def check_server(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        cookies_command_data: CookiesCommandData = context.chat_data.get("cookies_command_data")
        user_info = await self.service.user_service_db.get_user_info(user.id)
        cookies_command_data.user_info = user_info
        if update.message.text == "退出":
            await update.message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif update.message.text == "米游社":
            cookies_command_data.service = ServiceEnum.MIHOYOBBS
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
        javascript_android = "javascript:(()=>{prompt('',document.cookie)})();"
        help_message = f"*关于如何获取Cookies*\n\n" \
                       f"PC：\n" \
                       f"[1、打开{bbs_name}并登录]({bbs_url})\n" \
                       f"2、按F12打开开发者工具\n" \
                       f"3、{escape_markdown('将开发者工具切换至控制台(Console)页签', version=2)}\n" \
                       f"4、复制下方的代码，并将其粘贴在控制台中，按下回车\n" \
                       f"`{escape_markdown(javascript, version=2, entity_type='code')}`\n\n" \
                       f"Android：\n" \
                       f"[1、通过 Vim 浏览器打开{bbs_name}并登录]({bbs_url})\n" \
                       f"2、复制下方的代码，并将其粘贴在地址栏中，点击右侧箭头\n" \
                       f"`{escape_markdown(javascript_android, version=2, entity_type='code')}`"
        await update.message.reply_markdown_v2(help_message, disable_web_page_preview=True)
        return self.CHECK_COOKIES

    @conversation_error_handler
    async def check_cookies(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
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
        if cookies_command_data.service == ServiceEnum.MIHOYOBBS:
            client = genshin.ChineseClient(cookies=cookies)
        elif cookies_command_data.service == ServiceEnum.HOYOLAB:
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
        except AttributeError:
            await update.message.reply_text("Cookies错误，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except GenshinException as error:
            await update.message.reply_text(f"获取账号信息发生错误，错误信息为 {str(error)}，请检查Cookie或者账号是否正常",
                                            reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        cookies_command_data.cookies = cookies
        cookies_command_data.game_uid = user_info.uid
        reply_keyboard = [['确认', '退出']]
        await update.message.reply_text("获取角色基础信息成功，请检查是否正确！")
        Log.info(f"用户 {user.full_name}[{user.id}] 获取账号 {user_info.nickname}[{user_info.uid}] 信息成功")
        message = f"*角色信息*\n" \
                  f"角色名称：{escape_markdown(user_info.nickname, version=2)}\n" \
                  f"角色等级：{user_info.level}\n" \
                  f"UID：`{user_info.uid}`\n" \
                  f"服务器名称：`{user_info.server_name}`\n"
        await update.message.reply_markdown_v2(message,
                                               reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.COMMAND_RESULT

    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        cookies_command_data: CookiesCommandData = context.chat_data.get("cookies_command_data")
        if update.message.text == "退出":
            await update.message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif update.message.text == "确认":
            data = ujson.dumps(cookies_command_data.cookies)
            user_info = cookies_command_data.user_info
            service = ServiceEnum.NULL.value
            if cookies_command_data.service == ServiceEnum.MIHOYOBBS:
                user_info.mihoyo_game_uid = cookies_command_data.game_uid
                service = ServiceEnum.MIHOYOBBS.value
            elif cookies_command_data.service == ServiceEnum.HOYOLAB:
                user_info.hoyoverse_game_uid = cookies_command_data.game_uid
                service = ServiceEnum.HOYOLAB.value
            await self.service.user_service_db.set_user_info(user.id, user_info.mihoyo_game_uid,
                                                             user_info.hoyoverse_game_uid,
                                                             service)
            await self.service.user_service_db.set_cookie(user.id, data, cookies_command_data.service)
            Log.info(f"用户 {user.full_name}[{user.id}] 绑定账号成功")
            await update.message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await update.message.reply_text("回复错误，请重新输入")
            return self.COMMAND_RESULT
