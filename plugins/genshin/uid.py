from typing import Optional

import genshin
from genshin import DataNotPublic, GenshinException, types
from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, TelegramObject,
                      Update)
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.baseplugin import BasePlugin
from core.cookies.error import (CookiesNotFoundError,
                                TooManyRequestPublicCookies)
from core.cookies.services import CookiesService, PublicCookiesService
from core.plugin import Plugin, conversation, handler
from core.user.error import UserNotFoundError
from core.user.models import User
from core.user.services import UserService
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger
from utils.models.base import RegionEnum


class AddUserCommandData(TelegramObject):
    user: Optional[User] = None
    region: RegionEnum = RegionEnum.HYPERION
    game_uid: int = 0


CHECK_SERVER, CHECK_UID, COMMAND_RESULT = range(10100, 10103)


class SetUserUid(Plugin.Conversation, BasePlugin.Conversation):
    """UID用户绑定"""

    def __init__(
        self,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
        public_cookies_service: PublicCookiesService = None,
    ):
        self.public_cookies_service = public_cookies_service
        self.cookies_service = cookies_service
        self.user_service = user_service

    @conversation.entry_point
    @handler.command(command="setuid", filters=filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] 绑定账号命令请求")
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_uid_command_data")
        if add_user_command_data is None:
            cookies_command_data = AddUserCommandData()
            context.chat_data["add_uid_command_data"] = cookies_command_data
        text = (
            f"你好 {user.mention_markdown_v2()} "
            f'{escape_markdown("！请输入通行证UID（非游戏UID），BOT将会通过通行证UID查找游戏UID。请选择要绑定的服务器！或回复退出取消操作")}'
        )
        reply_keyboard = [["米游社", "HoYoLab"], ["退出"]]
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return CHECK_SERVER

    @conversation.state(state=CHECK_SERVER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_server(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_uid_command_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif message.text == "米游社":
            region = add_user_command_data.region = RegionEnum.HYPERION
        elif message.text == "HoYoLab":
            region = add_user_command_data.region = RegionEnum.HOYOLAB
        else:
            await message.reply_text("选择错误，请重新选择")
            return CHECK_SERVER
        try:
            user_info = await self.user_service.get_user_by_id(user.id)
            add_user_command_data.user = user_info
        except UserNotFoundError:
            user_info = None
        if user_info is not None:
            try:
                await self.cookies_service.get_cookies(user.id, region)
            except CookiesNotFoundError:
                pass
            else:
                await message.reply_text("你已经通过 Cookie 绑定了账号，无法继续下一步")
                return ConversationHandler.END
        await message.reply_text("请输入你的通行证UID（非游戏UID）", reply_markup=ReplyKeyboardRemove())
        return CHECK_UID

    @conversation.state(state=CHECK_UID)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_cookies(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_uid_command_data")
        region = add_user_command_data.region
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            hoyolab_uid = int(message.text)
        except ValueError:
            await message.reply_text("UID 格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            cookies = await self.public_cookies_service.get_cookies(user.id, region)
        except TooManyRequestPublicCookies:
            await message.reply_text("用户查询次数过多，请稍后重试", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if region == RegionEnum.HYPERION:
            client = genshin.Client(cookies=cookies.cookies, game=types.Game.GENSHIN, region=types.Region.CHINESE)
        elif region == RegionEnum.HOYOLAB:
            client = genshin.Client(
                cookies=cookies.cookies, game=types.Game.GENSHIN, region=types.Region.OVERSEAS, lang="zh-cn"
            )
        else:
            return ConversationHandler.END
        try:
            user_info = await client.get_record_card(hoyolab_uid)
        except DataNotPublic:
            await message.reply_text("角色未公开", reply_markup=ReplyKeyboardRemove())
            logger.warning(f"获取账号信息发生错误 hoyolab_uid[{hoyolab_uid}] 账户信息未公开")
            return ConversationHandler.END
        except GenshinException as exc:
            await message.reply_text("获取账号信息发生错误", reply_markup=ReplyKeyboardRemove())
            logger.error("获取账号信息发生错误")
            logger.exception(exc)
            return ConversationHandler.END
        if user_info.game != types.Game.GENSHIN:
            await message.reply_text("角色信息查询返回非原神游戏信息，" "请设置展示主界面为原神", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
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
        add_user_command_data.game_uid = user_info.uid
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return COMMAND_RESULT

    @conversation.state(state=COMMAND_RESULT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        add_user_command_data: AddUserCommandData = context.chat_data.get("add_uid_command_data")
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
            logger.info(f"用户 {user.full_name}[{user.id}] 绑定UID账号成功")
            await message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await message.reply_text("回复错误，请重新输入")
            return COMMAND_RESULT
