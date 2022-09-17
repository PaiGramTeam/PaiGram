import asyncio
import itertools
import os
import re
from asyncio import Lock
from ctypes import c_double
from datetime import datetime
from multiprocessing import Value
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple, Union

import ujson as json
from aiofiles import open as async_open
from bs4 import BeautifulSoup
from genshin import Client
from httpx import AsyncClient, HTTPError
from pydantic import BaseModel
from telegram import InputMediaDocument, InputMediaPhoto, Message, Update, User
from telegram.constants import ChatAction, ParseMode
from telegram.error import RetryAfter, TimedOut
from telegram.ext import CallbackContext

from core.assets import AssetsService
from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user.error import UserNotFoundError
from metadata.honey import HONEY_ID_MAP, HONEY_ROLE_NAME_MAP
from utils.bot import get_all_args
from utils.const import RESOURCE_DIR
from utils.decorators.admins import bot_admins_rights_check
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger

DATA_TYPE = Dict[str, List[List[str]]]
DATA_FILE_PATH = Path(__file__).joinpath('../daily.json').resolve()
AREA = ['蒙德', '璃月', '稻妻', '须弥']
DOMAINS = ['忘却之峡', '太山府', '菫色之庭', '昏识塔', '塞西莉亚苗圃', '震雷连山密宫', '砂流之庭', '有顶塔']
DOMAIN_AREA_MAP = dict(zip(DOMAINS, AREA * 2))

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


class DailyMaterial(Plugin, BasePlugin):
    """每日素材表"""
    data: DATA_TYPE
    locks: Tuple[Lock] = (Lock(), Lock())

    def __init__(self, assets: AssetsService, template: TemplateService):
        self.assets_service = assets
        self.template_service = template
        self.client = AsyncClient()

    async def __async_init__(self):
        data = None
        if not DATA_FILE_PATH.exists():
            async def task_daily():
                async with self.locks[0]:
                    logger.info("正在开始获取每日素材缓存")
                    self.data = await self._refresh_data()

            self.refresh_task = asyncio.create_task(task_daily())
        if not data and DATA_FILE_PATH.exists():
            async with async_open(DATA_FILE_PATH) as file:
                data = json.loads(await file.read())
            self.data = data

    async def _get_data_from_user(self, user: User) -> Tuple[Optional[Client], Dict[str, List[Any]]]:
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
                        icon=convert_path(await self.assets_service.character(cid).icon())
                    )
                )
                user_data['weapon'].append(
                    ItemData(
                        id=(wid := f"i_n{weapon.id}"), name=weapon.name, level=weapon.level, rarity=weapon.rarity,
                        refinement=weapon.refinement,
                        icon=convert_path(
                            await getattr(
                                self.assets_service.weapon(wid), 'icon' if weapon.ascension < 2 else 'awakened'
                            )()
                        ),
                        c_path=convert_path(await self.assets_service.character(cid).side())
                    )
                )
        except (UserNotFoundError, CookiesNotFoundError):
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
        return client, user_data

    @handler.command('daily_material', block=False)
    @restricts(restricts_time_of_groups=20, without_overlapping=True)
    @error_callable
    async def daily_material(self, update: Update, context: CallbackContext):
        user = update.effective_user
        args = get_all_args(context)
        now = datetime.now()

        if args and str(args[0]).isdigit():
            weekday = int(args[0]) - 1
            if weekday < 0:
                weekday = 0
            elif weekday > 6:
                weekday = 6
            time = title = f"星期{WEEK_MAP[weekday]}"
        else:  # 获取今日是星期几，判定了是否过了凌晨4点
            title = "今日"
            weekday = now.weekday() - (1 if now.hour < 4 else 0)
            weekday = 6 if weekday < 0 else weekday
            time = now.strftime("%m-%d %H:%M") + " 星期" + WEEK_MAP[weekday]
        full = args and args[-1] == 'full'

        if weekday == 6:
            notice = await update.message.reply_text(
                ("今天" if title == '今日' else '这天') + "是星期天, <b>全部素材都可以</b>刷哦~",
                parse_mode=ParseMode.HTML
            )
            self._add_delete_message_job(context, notice.chat_id, notice.message_id, 5)
            return

        if self.locks[0].locked():
            notice = await update.message.reply_text("派蒙正在摘抄每日素材表，以后再来探索吧~")
            self._add_delete_message_job(context, notice.chat_id, notice.message_id, 5)
            return

        if self.locks[1].locked():
            notice = await update.message.reply_text("派蒙正在搬运每日素材的图标，以后再来探索吧~")
            self._add_delete_message_job(context, notice.chat_id, notice.message_id, 5)
            return

        notice = await update.message.reply_text("派蒙可能需要找找图标素材，还请耐心等待哦~")
        await update.message.reply_chat_action(ChatAction.TYPING)

        # 获取已经缓存至本地的秘境素材信息
        local_data = {'character': [], 'weapon': []}
        if not self.data:
            logger.info("正在获取每日素材缓存")
            await self._refresh_data()
        for domain, sche in self.data.items():
            area = DOMAIN_AREA_MAP[domain]
            type_ = 'character' if DOMAINS.index(domain) < 4 else 'weapon'
            local_data[type_].append({'name': area, 'materials': sche[weekday][0], 'items': sche[weekday][1]})

        # 尝试获取用户已绑定的原神账号信息
        client, user_data = await self._get_data_from_user(user)

        await update.message.reply_chat_action(ChatAction.TYPING)
        render_data = RenderData(title=title, time=time, uid=client.uid if client else client)
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
                    item = HONEY_ID_MAP[type_][id_]
                    if item[1] < 4:  # 跳过 3 星及以下的武器
                        continue
                    items.append(ItemData(
                        id=id_, name=item[0], rarity=item[1],
                        icon=convert_path(await getattr(self.assets_service, f'{type_}')(id_).icon())
                    ))
                materials = []
                for mid in area_data['materials']:
                    path = convert_path(await self.assets_service.material(mid).icon())
                    material = HONEY_ID_MAP['material'][mid]
                    materials.append(ItemData(id=mid, icon=path, name=material[0], rarity=material[1]))
                areas.append(AreaData(name=area_data['name'], materials=materials, items=sort_item(items)))
            setattr(render_data, type_, areas)
        await update.message.reply_chat_action(ChatAction.TYPING)
        character_img_data = await self.template_service.render(
            'genshin/daily_material', 'character.html', {'data': render_data}, {'width': 1164, 'height': 500}
        )
        weapon_img_data = await self.template_service.render(
            'genshin/daily_material', 'weapon.html', {'data': render_data}, {'width': 1164, 'height': 500}
        )
        await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        if full:
            await update.message.reply_media_group([
                InputMediaDocument(character_img_data, filename="可培养角色.png"),
                InputMediaDocument(weapon_img_data, filename="可培养武器.png")
            ])
        else:
            await update.message.reply_media_group(
                [InputMediaPhoto(character_img_data), InputMediaPhoto(weapon_img_data)]
            )
        await notice.delete()

    @handler.command('refresh_daily_material', block=False)
    @bot_admins_rights_check
    async def refresh(self, update: Update, context: CallbackContext):
        message = update.effective_message
        if self.locks[0].locked():
            notice = await message.reply_text("派蒙还在抄每日素材表呢，我有在好好工作哦~")
            self._add_delete_message_job(context, notice.chat_id, notice.message_id, 10)
            return
        if self.locks[1].locked():
            notice = await message.reply_text("派蒙正在搬运每日素材图标，在努力工作呢！")
            self._add_delete_message_job(context, notice.chat_id, notice.message_id, 10)
            return
        async with self.locks[1]:
            notice = await message.reply_text("派蒙正在重新摘抄每日素材表，请稍等~", parse_mode=ParseMode.HTML)
            async with self.locks[0]:
                data = await self._refresh_data()
            notice = await notice.edit_text(
                "每日素材表" +
                ("摘抄<b>完成！</b>" if data else "坏掉了！等会它再长好了之后我再抄。。。") +
                '\n正搬运每日素材的图标中。。。',
                parse_mode=ParseMode.HTML
            )
            self.data = data or self.data
            await self._download_icon(notice)
            notice = await notice.edit_text(
                notice.text_html.split('\n')[0] + "\n每日素材图标搬运<b>完成！</b>",
                parse_mode=ParseMode.HTML
            )
            self._add_delete_message_job(context, notice.chat_id, notice.message_id, 10)

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
                    for day, _ in enumerate(schedules):
                        result[stage][day][1] = list(set(result[stage][day][1]))
                async with async_open(DATA_FILE_PATH, 'w', encoding='utf-8') as file:
                    await file.write(json.dumps(result))  # pylint: disable=PY-W0079
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

    async def _download_icon(self, message: Optional[Message] = None):
        from time import time as time_
        lock = asyncio.Lock()
        the_time = Value(c_double, time_() - 1)
        interval = 2

        async def task(_id, _item, _type):
            logger.debug(f"正在开始下载 \"{_item[0]}\" 的图标素材")
            async with lock:
                if message is not None and time_() >= the_time.value + interval:
                    text = '\n'.join(message.text_html.split('\n')[:2]) + f"\n正在搬运 <b>{_item[0]}</b> 的图标素材。。。"
                    try:
                        await message.edit_text(text, parse_mode=ParseMode.HTML)
                    except (TimedOut, RetryAfter):
                        pass
                    the_time.value = time_()
            asset = getattr(self.assets_service, _type)(_id)
            icon_types = list(filter(
                lambda x: not x.startswith('_') and x not in ['path'] and callable(getattr(asset, x)),
                dir(asset)
            ))
            icon_coroutines = map(lambda x: getattr(asset, x), icon_types)
            for coroutine in icon_coroutines:
                await coroutine()
            logger.debug(f"\"{_item[0]}\" 的图标素材下载成功")
            async with lock:
                if message is not None and time_() >= the_time.value + interval:
                    text = (
                            '\n'.join(message.text_html.split('\n')[:2]) +
                            f"\n正在搬运 <b>{_item[0]}</b> 的图标素材。。。<b>成功！</b>"
                    )
                    try:
                        await message.edit_text(text, parse_mode=ParseMode.HTML)
                    except (TimedOut, RetryAfter):
                        pass
                    the_time.value = time_()

        for type_, items in HONEY_ID_MAP.items():
            task_list = []
            for id_, item in items.items():
                task_list.append(asyncio.create_task(task(id_, item, type_)))
            await asyncio.gather(*task_list)

        logger.info("图标素材下载完成")


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
    title: str
    time: str
    uid: Optional[int] = None
    character: List[AreaData] = []
    weapon: List[AreaData] = []

    def __getitem__(self, item):
        return self.__getattribute__(item)
