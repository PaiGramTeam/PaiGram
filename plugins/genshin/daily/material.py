import itertools
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Union

import ujson as json
from aiofiles import open as async_open
from bs4 import BeautifulSoup
from httpx import AsyncClient, HTTPError
from pydantic import BaseModel
from telegram import InputMediaPhoto, Update
from telegram.constants import ChatAction, ParseMode

from core.assets import AssetsService
from core.base.aiobrowser import AioBrowser
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user.error import UserNotFoundError
from metadata.honey import HONEY_ID_MAP, HONEY_ROLE_NAME_MAP
from utils.const import RESOURCE_DIR
from utils.decorators.admins import bot_admins_rights_check
from utils.helpers import get_genshin_client
from utils.log import logger

DATA_TYPE = Dict[str, List[List[str]]]
DATA_FILE_PATH = Path(__file__).joinpath('../daily.json').resolve()
AREA = ['蒙德', '璃月', '稻妻', '须弥']
DOMAINS = ['忘却之峡', '太山府', '菫色之庭', '昏识塔', '塞西莉亚苗圃', '震雷连山密宫', '砂流之庭', '有顶塔']
DOMAIN_AREA_MAP = {k: v for k, v in zip(DOMAINS, AREA * 2)}

WEEK_MAP = ['一', '二', '三', '四', '五', '六', '日']


def convert_path(path: Union[str, Path]) -> str:
    return f"..{os.sep}..{os.sep}" + str(path.relative_to(RESOURCE_DIR))


def sort_item(items: List['ItemData']) -> Iterable['ItemData']:
    result_a = []
    for _, group_a in itertools.groupby(sorted(items, key=lambda x: x.rarity, reverse=True), lambda x: x.rarity):
        result_b = []
        for _, group_b in itertools.groupby(
                sorted(group_a, key=lambda x: x.level or -1, reverse=True), lambda x: x.level or -1
        ):
            result_b.append(sorted(group_b, key=lambda x: x.constellation or x.refinement or -1, reverse=True))
        result_a.append(itertools.chain(*result_b))
    return itertools.chain(*result_a)


class DailyMaterial(Plugin):
    """每日素材表"""
    data: DATA_TYPE

    def __init__(self, assets: AssetsService, template: TemplateService, browser: AioBrowser):
        self.browser = browser
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
        now = datetime.now()
        # 获取今日是星期几，判定了是否过了凌晨4点
        weekday = now.weekday() - (1 if now.hour < 4 else 0)
        weekday = 6 if weekday < 0 else weekday

        if weekday == 6:
            await update.message.reply_text("今天是星期天, <b>全部素材都可以</b>刷哦~", parse_mode=ParseMode.HTML)
            return

        time = now.strftime("%m-%d %H:%M") + " 星期" + WEEK_MAP[weekday]

        # 获取已经缓存至本地的秘境素材信息
        local_data = {'character': [], 'weapon': []}
        for domain, sche in self.data.items():
            area = DOMAIN_AREA_MAP[domain]
            type_ = 'character' if DOMAINS.index(domain) < 4 else 'weapon'
            local_data[type_].append({'name': area, 'materials': sche[weekday][0], 'items': sche[weekday][1]})

        # 尝试获取用户已绑定的原神账号信息
        client = None
        user_data = {'character': [], 'weapon': []}
        try:
            logger.debug("尝试获取已绑定的原神账号")
            client = await get_genshin_client(user.id)
            logger.debug(f"获取成功, UID: {client.uid}")
            characters = await client.get_genshin_characters(client.uid)
            for character in characters:
                cid = HONEY_ROLE_NAME_MAP[character.id][0]
                weapon = character.weapon
                user_data['character'].append(
                    ItemData(
                        id=cid, name=character.name, rarity=character.rarity, level=character.level,
                        constellation=character.constellation,
                        icon="file://" + str((c_icons := await self.assets_service.character_icon(cid))['icon'])
                    )
                )
                user_data['weapon'].append(
                    ItemData(
                        id=(wid := f"i_n{weapon.id}"), name=weapon.name, level=weapon.level, rarity=weapon.rarity,
                        refinement=weapon.refinement,
                        icon=convert_path(
                            (
                                await self.assets_service.weapon_icon(wid)
                            )['icon' if weapon.ascension < 2 else 'awakened']),
                        c_path=convert_path(c_icons['side'])
                    )
                )
            del character, weapon, characters
        except (UserNotFoundError, CookiesNotFoundError):
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")

        render_data = RenderData(time=time, uid=client.uid if client else client)
        for type_ in ['character', 'weapon']:
            areas = []
            for area_data in local_data[type_]:
                items = []
                for id_ in area_data['items']:
                    added = False
                    for i in user_data[type_]:
                        if id_ == i.id:
                            if i.rarity > 3:  # 跳过 3 星及以下的武器
                                items.append(i)
                            added = True
                            break
                    if added:
                        continue
                    d = HONEY_ID_MAP[type_][id_]
                    if d[1] < 4:  # 跳过 3 星及以下的武器
                        continue
                    items.append(ItemData(
                        id=id_, name=d[0], rarity=d[1],
                        icon=convert_path((await (getattr(self.assets_service, f'{type_}_icon')(id_)))['icon'])
                    ))
                materials = []
                for mid in area_data['materials']:
                    path = convert_path(await self.assets_service.material_icon(mid))
                    material = HONEY_ID_MAP['material'][mid]
                    materials.append(ItemData(id=mid, icon=path, name=material[0], rarity=material[1]))
                areas.append(AreaData(name=area_data['name'], materials=materials, items=sort_item(items)))
            del items, materials
            setattr(render_data, type_, areas)
        del areas
        character_img_data = await self.template_service.render(
            'genshin/daily_material', 'character.html', {'data': render_data}, {'width': 1164, 'height': 500}
        )
        weapon_img_data = await self.template_service.render(
            'genshin/daily_material', 'weapon.html', {'data': render_data}, {'width': 1164, 'height': 500}
        )
        await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await update.message.reply_media_group([InputMediaPhoto(character_img_data), InputMediaPhoto(weapon_img_data)])

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


class ItemData(BaseModel):
    id: str
    name: str
    rarity: int
    icon: str
    level: Optional[int] = None
    constellation: Optional[int] = None
    refinement: Optional[int] = None
    c_path: Optional[str] = None


class AreaData(BaseModel):
    name: Literal['蒙德', '璃月', '稻妻', '须弥']
    materials: List[ItemData] = []
    items: Iterable[ItemData] = []


class RenderData(BaseModel):
    time: str
    uid: Optional[int] = None
    character: List[AreaData] = []
    weapon: List[AreaData] = []

    def __getitem__(self, item):
        return self.__getattribute__(item)
