import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal

import ujson as json
from aiofiles import open as async_open
from bs4 import BeautifulSoup
from httpx import AsyncClient, HTTPError
from pydantic import BaseModel
from telegram import Update
from telegram.constants import ParseMode

from core.assets import AssetsService
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user.error import UserNotFoundError
from metadata.shortname import honey_role_map
from utils.decorators.admins import bot_admins_rights_check
from utils.helpers import get_genshin_client
from utils.log import logger

DATA_FILE_PATH = Path(__file__).joinpath('../data.json').resolve()
DATA_TYPE = Dict[str, List[List[str]]]
AREA = ['蒙德', '璃月', '稻妻', '须弥']
DOMAINS = ['忘却之峡', '太山府', '菫色之庭', '昏识塔', '塞西莉亚苗圃', '震雷连山密宫', '砂流之庭', '有顶塔']
DOMAIN_AREA_MAP = {k: v for k in DOMAINS for v in AREA * 2}


class RenderData(BaseModel):
    user: List[str]
    full: List[str]


class AreaData(BaseModel):
    area: Literal['蒙德', '璃月', '稻妻', '须弥']
    data: RenderData


class DailyMaterial(Plugin):
    """每日素材表"""
    data: DATA_TYPE

    def __init__(self, assets: AssetsService, template: TemplateService):
        self.assets_service = assets
        self.template_service = template
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
        weekday = (now := datetime.now()).weekday() - (1 if now.hour < 4 else 0)
        weekday = 6 if weekday < 0 else weekday

        sche_data = {'character': {}, 'weapon': {}}
        for domain, sche in self.data.items():
            area = DOMAIN_AREA_MAP[domain]
            key = 'character' if DOMAINS.index(domain) < 4 else 'weapon'
            if area not in sche_data[key].keys():
                sche_data[key][area] = {}
            sche_data[key][area].update({domain: sche[weekday]})

        user_data = {'character': [], 'weapon': []}  # [[角色], [武器]]
        try:
            client = await get_genshin_client(user.id)
            characters = await client.get_genshin_characters(client.uid)
            for character in characters:
                weapon = character.weapon
                user_data['character'].append([
                    cid := honey_role_map[character.id][0],
                    character.name, character.level, character.constellation, character.rarity
                ])
                user_data['weapon'].append([
                    f"i_n{weapon.id}", weapon.name, weapon.level, weapon.refinement, weapon.rarity, cid
                ])
        except (UserNotFoundError, CookiesNotFoundError):
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")

        render_data = {
            'character': {j: [[], []] for i, j in enumerate(DOMAINS) if i < 4},
            'weapon': {j: [[], []] for i, j in enumerate(DOMAINS) if i >= 4}
        }
        for i, domain in enumerate(DOMAINS):
            key = 'character' if i < 4 else 'weapon'
            area = DOMAIN_AREA_MAP[domain]
            for id_ in sche_data[key][area][domain][1]:
                render_data[key][domain][id_ not in map(lambda x: x[0], user_data[key])].append(id_)
        render_data.update({'user_data': user_data})
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

    async def _refresh_data(self, retry: int = 5) -> DATA_TYPE:
        from bs4 import Tag
        from asyncio import sleep
        result = {}
        for i in range(retry):
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
                if i <= retry - 1:
                    logger.warning("每日素材刷新失败, 正在重试")
                else:
                    logger.error("每日素材刷新失败, 请稍后重试")
                continue
        # noinspection PyTypeChecker
        return result
