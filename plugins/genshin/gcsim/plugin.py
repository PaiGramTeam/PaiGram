import time
import copy
import shutil
import asyncio
import subprocess
import multiprocessing
from hashlib import md5
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, TYPE_CHECKING, List

import gcsim_pypi
from enkanetwork import Assets
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User, Message, CallbackQuery
from telegram.ext import CallbackContext
from telegram.constants import ChatAction
from telegram.helpers import create_deep_linked_url
from enkanetwork import EnkaNetworkResponse

from core.config import config
from core.plugin import Plugin, handler
from core.services.players import PlayersService
from utils.log import logger
from utils.const import PROJECT_ROOT
from metadata.shortname import idToName
from modules.playercards.file import PlayerCardsFile
from modules.gcsim.file import PlayerGCSimScripts
from plugins.genshin.model.gcsim import GCSim
from plugins.genshin.model.base import CharacterInfo
from plugins.genshin.model.converters.enka import EnkaConverter
from plugins.genshin.model.converters.gcsim import GCSimConverter

if TYPE_CHECKING:
    from telegram.ext import ContextTypes

__all__ = ("GCSimPlugin",)

GCSIM_SCRIPTS_PATH = PROJECT_ROOT.joinpath("plugins", "genshin", "gcsim", "scripts")


@dataclass
class GCSimFit:
    script_key: str
    fit_count: int
    characters: List[str]
    total_levels: int
    total_weapon_levels: int


def process_script(f: Path) -> Optional[GCSim]:
    try:
        script = GCSimConverter.from_gcsim_script(f.read_text())
        return script
    except ValueError as e:
        logger.error("无法解析 GCSim 脚本 %s: %s", f.name, e)
        return None


class GCSimPlugin(Plugin):
    def __init__(self, player_service: PlayersService, max_concurrent_gcsim: Optional[int] = None):
        self.player_service = player_service
        self.player_cards_file = PlayerCardsFile()
        self.player_gcsim_scripts = PlayerGCSimScripts()
        self.gcsim_version: Optional[str] = None
        self.gcsim_bin_path: Optional[Path] = None
        self.scripts: Dict[str, GCSim] = {}
        self.gcsim_queue = []
        self.current_gcsim: Dict[str, str] = {}
        self.max_concurrent_gcsim = (
            max_concurrent_gcsim
            if max_concurrent_gcsim is not None
            else 1
            if multiprocessing.cpu_count() == 1
            else multiprocessing.cpu_count() / 2
        )

    async def _no_account_return(self, message: Message, context: "ContextTypes.DEFAULT_TYPE"):
        buttons = [
            [
                InlineKeyboardButton(
                    "点我绑定账号",
                    url=create_deep_linked_url(context.bot.username, "set_uid"),
                )
            ]
        ]
        await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))

    async def _no_character_reurn(self, user_id: str, uid: str, message: Message):
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

    async def _get_uid(self, user: User) -> Optional[str]:
        player_info = await self.player_service.get_player(user.id)
        if player_info is None:
            return None
        return player_info.player_id

    async def _load_characters(self, uid: str) -> List[CharacterInfo]:
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

    def _gen_buttons(self, user_id: str, uid: str, fits: List[GCSimFit]) -> List[List[InlineKeyboardButton]]:
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

    async def _process_gcsim_queue(self):
        while len(self.current_gcsim) < self.max_concurrent_gcsim and self.gcsim_queue:
            callback_query, user_id, uid, script_key = self.gcsim_queue.pop(0)
            await self._run_gcsim(callback_query, user_id, uid, script_key)

    async def _run_gcsim(self, callback_query: CallbackQuery, user_id: str, uid: str, script_key: str):
        script = self.scripts.get(script_key)
        if script is None:
            await callback_query.answer(f"未找到脚本: {script_key}", show_alert=True)
            return
        character_infos = await self._load_characters(uid)
        merged_script = GCSimConverter.merge_character_infos(script, character_infos)
        await self.player_gcsim_scripts.write_script(uid, script_key, str(merged_script))
        process = await asyncio.create_subprocess_exec(
            self.gcsim_bin_path,
            "-c",
            self.player_gcsim_scripts.get_script_path(uid, script_key).absolute().as_posix(),
            "-out",
            self.player_gcsim_scripts.get_result_path(uid, script_key).absolute().as_posix(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.current_gcsim[(uid, script_key)] = process
        asyncio.create_task(self._gcsim_callback(callback_query, user_id, uid, script_key))

    async def _gcsim_callback(self, callback_query: CallbackQuery, user_id: str, uid: str, script_key: str):
        process = self.current_gcsim.pop((uid, script_key))
        stdout, stderr = await process.communicate()
        if stdout:
            logger.debug("GCSim 脚本输出: %s", stdout.decode("utf-8"))
            await callback_query.edit_message_text(
                f"脚本 {script_key} 运行完毕\n\n" f"```\n" f"{stdout.decode('utf-8')}\n" f"```",
                parse_mode="markdown",
            )
        if stderr:
            logger.error("GCSim 脚本错误: %s", stderr.decode("utf-8"))
            await callback_query.edit_message_text(
                f"脚本 {script_key} 运行出错\n\n" f"```\n" f"{stderr.decode('utf-8')}\n" f"```",
                parse_mode="markdown",
            )

    async def initialize(self):
        gcsim_pypi_path = Path(gcsim_pypi.__file__).parent

        self.gcsim_bin_path = gcsim_pypi_path.joinpath("bin").joinpath("gcsim")
        result = subprocess.run([self.gcsim_bin_path, "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            self.gcsim_version = result.stdout.splitlines()[0]

        now = time.time()
        for f in GCSIM_SCRIPTS_PATH.iterdir():
            if f.is_file():
                try:
                    script = GCSimConverter.from_gcsim_script(f.read_text())
                    self.scripts[f.stem] = script
                except ValueError as e:
                    logger.error("无法解析 GCSim 脚本 %s: %s", f.name, e)
        logger.debug("加载 GCSim 脚本耗时 %.2f 秒", time.time() - now)

    @handler.command(command="gcsim", block=False)
    async def gcsim(self, update: Update, context: "ContextTypes.DEFAULT_TYPE"):
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 发出 gcsim 命令", user.full_name, user.id)

        uid = await self._get_uid(user)
        if uid is None:
            return await self._no_account_return(message, context)

        character_infos = await self._load_characters(uid)
        if not character_infos:
            return await self._no_character_reurn(user.id, uid, message, context)

        fits = []
        for key, script in self.scripts.items():
            # 空和莹会被认为是两个角色
            fit_characters = []
            for ch in character_infos:
                if GCSimConverter.from_character(ch.character) in [c.character for c in script.characters]:
                    fit_characters.append(ch) 
            if fit_characters:
                fits.append(
                    GCSimFit(
                        script_key=key,
                        characters=[idToName(ch.id) for ch in fit_characters],
                        fit_count=len(fit_characters),
                        total_levels=sum(ch.level for ch in script.characters),
                        total_weapon_levels=sum(ch.weapon_info.level for ch in script.characters),
                    )
                )
        fits = sorted(
            fits,
            key=lambda x: (x.fit_count, x.total_levels, x.total_weapon_levels),
            reverse=True,
        )
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
        if str(user.id) != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return

        logger.info("用户 %s[%s] GCSim运行请求 || %s", user.full_name, user.id, callback_query.data)
        await message.reply_chat_action(ChatAction.TYPING)
        self.gcsim_queue.append((callback_query, user_id, uid, script_key))
        await self._process_gcsim_queue()
