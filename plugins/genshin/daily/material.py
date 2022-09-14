import re
from datetime import date
from pathlib import Path
from typing import Dict, List

import ujson as json
from aiofiles import open as async_open
from bs4 import BeautifulSoup
from httpx import AsyncClient, HTTPError
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from core.assets import AssetsService
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.user.error import UserNotFoundError
from utils.decorators.admins import bot_admins_rights_check
from utils.helpers import get_genshin_client
from utils.log import logger

DATA_FILE_PATH = Path(__file__).joinpath('../data.json').resolve()
DATA_TYPE = Dict[str, List[List[str]]]


class DailyMaterial(Plugin):
    """每日素材表"""
    data: DATA_TYPE

    def __init__(self, assets: AssetsService, ):
        self.assets_service = assets
        self.client = AsyncClient()

    async def __async_init__(self):
        data = None
        if not DATA_FILE_PATH.exists():
            logger.info("正在开始获取每日素材缓存")
            data = await self._refresh_data()
        if not data and DATA_FILE_PATH.exists():
            async with async_open(DATA_FILE_PATH) as file:
                data = json.loads(await file.read())
        self.data = data

    @handler.command('daily_material', block=False)
    async def daily_material(self, update: Update, _):
        user = update.effective_user
        weekday = date.today().weekday()

        sche_data = {}
        for domain, sche in self.data.items():
            sche_data.update({domain: sche[weekday]})

        user_data = [[], []]  # [[角色], [武器]]
        try:
            client = await get_genshin_client(user.id)
            characters = await client.get_genshin_characters(client.uid)
            for character in characters:
                weapon = character.weapon
                user_data[0].append([
                    character.id, character.name, character.level, character.constellation, character.rarity
                ])
                user_data[1].append([
                    weapon.id, weapon.name, weapon.level, weapon.refinement, weapon.rarity, character.id
                ])
        except (UserNotFoundError, CookiesNotFoundError):
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
        breakpoint()

    @handler.command('refresh_daily_material', block=False)
    @bot_admins_rights_check
    async def refresh(self, update: Update, _):
        message = update.effective_message
        await message.reply_text("正在刷新<b>每日素材</b>缓存，请稍等", parse_mode=ParseMode.HTML)
        data = await self._refresh_data()
        await message.reply_text(
            "<b>每日素材</b>缓存刷新失败" + ("" if data else ", 请稍后重试"), parse_mode=ParseMode.HTML
        )

    async def _refresh_data(self) -> DATA_TYPE:
        from bs4 import Tag
        from asyncio import sleep
        result = {}
        for i in range(5):
            try:
                response = await self.client.get("https://genshin.honeyhunterworld.com/?lang=CHS")
                soup = BeautifulSoup(response.text, 'lxml')
                calendar = soup.select(".calendar_day_wrap")[0]
                key: str = ''
                for tag in calendar:
                    tag: Tag
                    if tag.name == 'span':
                        key = tag.find('a').text
                        result[key] = [[[], []] for _ in range(7)]
                        for day, div in enumerate(tag.find_all('div')):
                            result[key][day][0] = [re.findall(r"/(.*)?/", a['href'])[0] for a in div.find_all('a')]
                    else:
                        id_ = re.findall(r"/(.*)?/", tag['href'])[0]
                        if tag.text.strip() == '旅行者':
                            continue
                        for day in map(int, tag.find('div')['data-days']):
                            result[key][day][1].append(id_)
                for stage, schedules in result.items():
                    for day, sche in enumerate(schedules):
                        result[stage][day][1] = list(set(i for i in result[stage][day][1]))
                async with async_open(DATA_FILE_PATH, 'w', encoding='utf-8') as file:
                    await file.write(json.dumps(result))
                logger.info("每日素材刷新成功")
                break
            except HTTPError:
                await sleep(1)
                if i != 4:
                    logger.warning("每日素材刷新失败, 正在重试")
                else:
                    logger.error("每日素材刷新失败, 请稍后重试")
                continue
        # noinspection PyTypeChecker
        return result
