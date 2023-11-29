import time
import copy
import shutil
import asyncio
import platform
import subprocess
import multiprocessing
from hashlib import md5
from pathlib import Path
from dataclasses import dataclass
from asyncio.subprocess import Process  # noqa
from typing import Optional, Dict, TYPE_CHECKING, List, Tuple, Union

import aiofiles
import gcsim_pypi
from enkanetwork import Assets, EnkaNetworkResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User, Message, CallbackQuery
from telegram.ext import CallbackContext
from telegram.constants import ChatAction
from telegram.helpers import create_deep_linked_url

from core.config import config
from core.plugin import Plugin, handler
from core.services.players import PlayersService
from gram_core.services.template.services import TemplateService
from utils.log import logger
from utils.const import PROJECT_ROOT
from metadata.shortname import idToName
from modules.playercards.file import PlayerCardsFile
from modules.gcsim.file import PlayerGCSimScripts
from plugins.genshin.gcsim.runner import GCSimRunner, GCSimFit
from plugins.genshin.gcsim.renderer import GCSimResultRenderer
from plugins.genshin.model.gcsim import GCSim
from plugins.genshin.model.base import CharacterInfo
from plugins.genshin.model.converters.enka import EnkaConverter
from plugins.genshin.model.converters.gcsim import GCSimConverter

if TYPE_CHECKING:
    from telegram.ext import ContextTypes

__all__ = ("GCSimPlugin",)


async def _no_account_return(message: Message, context: "ContextTypes.DEFAULT_TYPE"):
    buttons = [
        [
            InlineKeyboardButton(
                "点我绑定账号",
                url=create_deep_linked_url(context.bot.username, "set_uid"),
            )
        ]
    ]
    await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))


async def _no_character_return(user_id: int, uid: int, message: Message):
    photo = open("resources/img/kitsune.png", "rb")
    buttons = [
        [
            InlineKeyboardButton(
                "更新面板",
                callback_data=f"update_player_card|{user_id}|{uid}",
            )
        ]
    ]
    await message.reply_photo(
        photo=photo,
        caption="角色列表未找到，请尝试点击下方按钮从 Enka.Network 更新角色列表",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


class GCSimPlugin(Plugin):
    def __init__(self, player_service: PlayersService, template_service: TemplateService):
        self.player_service = player_service
        self.template_service = template_service
        self.player_cards_file = PlayerCardsFile()
        self.player_gcsim_scripts = PlayerGCSimScripts()
        self.gcsim_runner = GCSimRunner()
        self.gcsim_renderer = GCSimResultRenderer()

    async def initialize(self):
        await self.gcsim_runner.initialize()

    def _gen_buttons(self, user_id: int, uid: int, fits: List[GCSimFit]) -> List[List[InlineKeyboardButton]]:
        buttons = []
        for fit in fits:
            button = InlineKeyboardButton(
                f"{fit.script_key} ({','.join(fit.characters)})",
                callback_data=f"enqueue_gcsim|{user_id}|{uid}|{fit.script_key}",
            )
            if not buttons or len(buttons[-1]) >= 1:
                buttons.append([])
            buttons[-1].append(button)
        return buttons

    async def _get_uid(self, user: User) -> Optional[int]:
        player_info = await self.player_service.get_player(user.id)
        if player_info is None:
            return None
        return player_info.player_id

    async def _load_characters(self, uid: Union[int, str]) -> List[CharacterInfo]:
        original_data = await self.player_cards_file.load_history_info(uid)
        if original_data is None or len(original_data.get("avatarInfoList", [])) == 0:
            return []
        enka_response = EnkaNetworkResponse.parse_obj(copy.deepcopy(original_data))
        character_infos = []
        for avatar_info in enka_response.characters:
            try:
                character_infos.append(EnkaConverter.to_character_info(avatar_info))
            except ValueError:
                logger.error("无法解析 Enka.Network 角色信息: %s", avatar_info)
        return character_infos

    @handler.command(command="gcsim", block=False)
    async def gcsim(self, update: Update, context: "ContextTypes.DEFAULT_TYPE"):
        message = update.effective_message
        if not self.gcsim_runner.initialized:
            await message.reply_text("GCSim 未初始化，请稍候再试或重启派蒙")
            return
        if context.user_data.get('overlapping', False):
            reply = await message.reply_text("旅行者已经有脚本正在运行，请让派蒙稍微休息一下")
            await asyncio.sleep(10)
            await reply.delete()
            # also delete original message?
            await message.delete()
            return

        user = update.effective_user
        logger.info("用户 %s[%s] 发出 gcsim 命令", user.full_name, user.id)

        uid = await self._get_uid(user)
        if uid is None:
            return await _no_account_return(message, context)

        character_infos = await self._load_characters(uid)
        if not character_infos:
            return await _no_character_return(user.id, uid, message)

        fits = await self.gcsim_runner.calculate_fits(character_infos)
        buttons = self._gen_buttons(user.id, uid, fits[:10])
        await message.reply_text(
            "请选择 GCSim 脚本",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    @handler.callback_query(pattern=r"^enqueue_gcsim\|", block=False)
    async def enqueue_gcsim(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message
        user_id, uid, script_key = callback_query.data.split("|")[1:]
        logger.info("用户 %s[%s] GCSim运行请求 || %s", user.full_name, user.id, callback_query.data)
        if str(user.id) != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return

        logger.info("用户 %s[%s] GCSim运行请求 || %s", user.full_name, user.id, callback_query.data)
        character_infos = await self._load_characters(uid)
        if not character_infos:
            return await _no_character_return(user.id, uid, message)

        await callback_query.edit_message_text("GCSim 运行中...", reply_markup=InlineKeyboardMarkup([]))
        result = await self.gcsim_runner.run(user_id, uid, script_key, character_infos)
        if result.error:
            await callback_query.edit_message_text(result.error)
        else:
            await callback_query.edit_message_text(f"GCSim {result.script_key} 运行完成")

        result_path = self.player_gcsim_scripts.get_result_path(uid, script_key)
        if not result_path.exists():
            await callback_query.answer(text="运行结果似乎在提瓦特之外，派蒙找不到了。", show_alert=True)

        await self.gcsim_renderer.render(result_path)
