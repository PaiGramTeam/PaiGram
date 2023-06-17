from typing import Optional

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, TelegramObject, Update
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.basemodel import RegionEnum
from core.plugin import Plugin, conversation, handler
from core.services.cookies.services import CookiesService
from core.services.devices import DevicesService
from core.services.devices.models import DevicesDataBase as Devices
from core.services.players.services import PlayersService
from modules.apihelper.utility.devices import devices_methods
from utils.log import logger

__all__ = ("AccountDevicesPlugin",)


class AccountDevicesPluginData(TelegramObject):
    device_id: str = ""
    device_fp: str = ""
    device_name: Optional[str] = None
    account_id: int = 0

    def reset(self):
        self.device_id = ""
        self.device_fp = ""
        self.device_name = None
        self.account_id = 0


CHECK_SERVER, INPUT_DEVICES, COMMAND_RESULT = range(10100, 10103)


class AccountDevicesPlugin(Plugin.Conversation):
    """设备绑定"""

    def __init__(
        self,
        players_service: PlayersService = None,
        cookies_service: CookiesService = None,
        devices_service: DevicesService = None,
    ):
        self.cookies_service = cookies_service
        self.players_service = players_service
        self.devices_service = devices_service
        devices_methods.service = devices_service

    @staticmethod
    def parse_headers(data: AccountDevicesPluginData, headers_text: str) -> None:
        headers = {}
        for line in headers_text.splitlines():
            if not line:
                continue
            try:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
            except ValueError:
                continue
        must_keys = {"x-rpc-device_id": 36, "x-rpc-device_fp": 13}
        optional_keys = ["x-rpc-device_name"]
        for k, v in must_keys.items():
            if (k not in headers) or (not headers.get(k)):
                raise ValueError
            if len(headers.get(k)) != v:
                raise ValueError
        for k in optional_keys:
            if k not in headers:
                continue
            elif headers.get(k) and len(headers.get(k)) > 64:
                raise ValueError

        data.device_id = headers.get("x-rpc-device_id")
        data.device_fp = headers.get("x-rpc-device_fp")
        data.device_name = headers.get("x-rpc-device_name")

    @conversation.entry_point
    @handler.command(command="setdevice", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="setdevices", filters=filters.ChatType.PRIVATE, block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 绑定设备命令请求", user.full_name, user.id)
        account_devices_plugin_data: AccountDevicesPluginData = context.chat_data.get("account_devices_plugin_data")
        if account_devices_plugin_data is None:
            account_devices_plugin_data = AccountDevicesPluginData()
            context.chat_data["account_devices_plugin_data"] = account_devices_plugin_data
        else:
            account_devices_plugin_data.reset()

        text = f'你好 {user.mention_markdown_v2()} {escape_markdown("！请选择要绑定的服务器！或回复退出取消操作")}'
        reply_keyboard = [["米游社"], ["退出"]]
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return CHECK_SERVER

    @conversation.state(state=CHECK_SERVER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def check_server(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        account_devices_plugin_data: AccountDevicesPluginData = context.chat_data.get("account_devices_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "米游社":
            region = RegionEnum.HYPERION
            bbs_name = "米游社"
        else:
            await message.reply_text("选择错误，请重新选择")
            return CHECK_SERVER
        player_info = await self.players_service.get(user.id, region=region)
        if player_info:
            cookies_database = await self.cookies_service.get(user.id, player_info.account_id, region)
            if not cookies_database:
                await message.reply_text(f"你还没有绑定 {bbs_name} 的Cookies，请先绑定Cookies")
                return ConversationHandler.END
            account_devices_plugin_data.account_id = player_info.account_id
        else:
            await message.reply_text(f"你还没有绑定 {bbs_name} 的Cookies，请先绑定Cookies")
            return ConversationHandler.END
        help_message = (
            "<b>关于如何获取Device</b>\n"
            "<b>此操作只能在PC上进行。</b>\n\n"
            "PC：\n"
            "1、打开<a href='https://user.mihoyo.com/'>通行证</a>并登录\n"
            "2、进入通行证按F12打开开发者工具\n"
            "3、将开发者工具切换至网络(Network)并点击过滤栏中的 Fetch/XHR 并刷新页面\n"
            "4、在请求列表中找到 login_by_cookie\n"
            "5、右键并复制请求标头(Request Headers)\n"
            "<u>如发现没有此请求大概因为缓存的存在需要你点击禁用缓存(Disable Cache)再次刷新页面</u>"
        )
        await message.reply_html(help_message, disable_web_page_preview=True)
        await message.reply_text(f"请输入{bbs_name}的请求标头！或回复退出取消操作", reply_markup=ReplyKeyboardRemove())
        return INPUT_DEVICES

    @conversation.state(state=INPUT_DEVICES)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def input_cookies(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        account_devices_plugin_data: AccountDevicesPluginData = context.chat_data.get("account_devices_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            self.parse_headers(account_devices_plugin_data, message.text)
        except ValueError as exc:
            logger.info("用户 %s[%s] Devices解析出现错误\ntext:%s", user.full_name, user.id, message.text)
            logger.debug("解析Devices出现错误", exc_info=exc)
            await message.reply_text("解析Devices出现错误，请检查是否正确", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        reply_keyboard = [["确认", "退出"]]
        await message.reply_markdown_v2(
            "请确认修改！", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return COMMAND_RESULT

    @conversation.state(state=COMMAND_RESULT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        account_devices_plugin_data: AccountDevicesPluginData = context.chat_data.get("account_devices_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "确认":
            device = await self.devices_service.get(account_devices_plugin_data.account_id)
            if device:
                device.device_id = account_devices_plugin_data.device_id
                device.device_fp = account_devices_plugin_data.device_fp
                device.device_name = account_devices_plugin_data.device_name
                await self.devices_service.update(device)
                logger.success("用户 %s[%s] 更新Devices", user.full_name, user.id)
            else:
                device = Devices(
                    account_id=account_devices_plugin_data.account_id,
                    device_id=account_devices_plugin_data.device_id,
                    device_fp=account_devices_plugin_data.device_fp,
                    device_name=account_devices_plugin_data.device_name,
                )
                await self.devices_service.add(device)
                logger.info("用户 %s[%s] 绑定Devices成功", user.full_name, user.id)
            await message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("回复错误，请重新输入")
        return COMMAND_RESULT
