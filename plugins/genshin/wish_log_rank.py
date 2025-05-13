from typing import TYPE_CHECKING, List, Tuple, Dict, Optional

from pydantic import BaseModel
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import filters

from core.dependence.assets.impl.genshin import AssetsService
from core.plugin import Plugin, handler
from core.services.template.models import FileType
from core.services.template.services import TemplateService
from gram_core.config import config
from gram_core.dependence.redisdb import RedisDB
from gram_core.services.gacha_log_rank.models import GachaLogRank, GachaLogTypeEnum, GachaLogQueryTypeEnum
from gram_core.services.gacha_log_rank.services import GachaLogRankService
from gram_core.services.players import PlayersService
from modules.gacha_log.ranks import GachaLogRanks
from plugins.tools.player_info import PlayerInfoSystem
from utils.log import logger
from utils.uid import mask_number

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class RankPlayerModel(BaseModel):
    player_id: int
    num: int
    nickname: Optional[str]
    score_1: int
    score_2: float
    score_3: float
    score_4: float
    score_5: float

    @property
    def mask_uid(self) -> str:
        return mask_number(self.player_id)


class RankDataModel(BaseModel):
    players: List[RankPlayerModel]
    count: int


class WishLogRankPlugin(Plugin):
    """抽卡数据排行"""

    TYPES = [
        ("角色-总抽数", GachaLogTypeEnum.CHARACTER, GachaLogQueryTypeEnum.TOTAL),
        ("角色-五星平均", GachaLogTypeEnum.CHARACTER, GachaLogQueryTypeEnum.FIVE_STAR_AVG),
        ("角色-UP平均", GachaLogTypeEnum.CHARACTER, GachaLogQueryTypeEnum.UP_STAR_AVG),
        ("角色-小保底百分比", GachaLogTypeEnum.CHARACTER, GachaLogQueryTypeEnum.NO_WARP),
        ("武器-总抽数", GachaLogTypeEnum.WEAPON, GachaLogQueryTypeEnum.TOTAL),
        ("武器-五星平均", GachaLogTypeEnum.WEAPON, GachaLogQueryTypeEnum.FIVE_STAR_AVG),
        ("常驻-总抽数", GachaLogTypeEnum.DEFAULT, GachaLogQueryTypeEnum.TOTAL),
        ("常驻-五星平均", GachaLogTypeEnum.DEFAULT, GachaLogQueryTypeEnum.FIVE_STAR_AVG),
        ("集录-总抽数", GachaLogTypeEnum.HUN, GachaLogQueryTypeEnum.TOTAL),
        ("集录-五星平均", GachaLogTypeEnum.HUN, GachaLogQueryTypeEnum.FIVE_STAR_AVG),
    ]

    def __init__(
        self,
        assets_service: AssetsService = None,
        template_service: TemplateService = None,
        player_service: PlayersService = None,
        redis: RedisDB = None,
        player_info: PlayerInfoSystem = None,
        gacha_log_rank_service: GachaLogRankService = None,
    ) -> None:
        self.assets_service = assets_service
        self.template_service = template_service
        self.player_service = player_service
        self.redis = redis.client
        self.player_info = player_info
        self.gacha_log_rank_service = gacha_log_rank_service
        self.limit = 20
        self.key = "plugins:gacha_log_rank"
        self.expire = 30 * 60  # 30 分钟
        self.expire2 = 5 * 60  # 5 分钟
        self.wish_photo = None

    async def get_nickname_from_uid(self, player_id: int) -> str:
        nickname = "Unknown"
        try:
            _, _, nickname, _ = await self.player_info.get_player_info(player_id, None, "")
        except Exception:
            logger.warning("获取玩家昵称失败 player_id[%s]", player_id)
        return nickname

    @staticmethod
    def mysql_to_model(rank: "GachaLogRank", num: int, nickname: str) -> RankPlayerModel:
        return RankPlayerModel(
            player_id=rank.player_id,
            num=num,
            nickname=nickname,
            score_1=rank.score_1 or 0,
            score_2=(rank.score_2 / 100.0) if rank.score_2 else 0,
            score_3=(rank.score_3 / 100.0) if rank.score_3 else 0,
            score_4=(rank.score_4 / 100.0) if rank.score_4 else 0,
            score_5=(rank.score_5 / 100.0) if rank.score_5 else 0,
        )

    @staticmethod
    def get_desc_type(query_type: "GachaLogQueryTypeEnum") -> bool:
        desc = True
        if query_type not in (GachaLogQueryTypeEnum.TOTAL, GachaLogQueryTypeEnum.NO_WARP):
            desc = False
        return desc

    async def get_first_rank_players_from_sql(
        self, rank_type: "GachaLogTypeEnum", query_type: "GachaLogQueryTypeEnum", desc: bool
    ) -> RankDataModel:
        real_desc = self.get_desc_type(query_type)
        if desc:
            real_desc = not real_desc
        ranks_uids = await self.gacha_log_rank_service.get_ranks_cache(rank_type, query_type, desc=real_desc)
        count = await self.gacha_log_rank_service.get_ranks_length_cache(rank_type, query_type)
        uid_list = [int(uid) for uid, _ in ranks_uids]
        ranks = await self.gacha_log_rank_service.get_ranks_by_ids(rank_type, uid_list)
        players = []
        for rank in ranks:
            nickname = await self.get_nickname_from_uid(rank.player_id)
            players.append(self.mysql_to_model(rank, uid_list.index(rank.player_id) + 1, nickname))
        players.sort(key=lambda x: x.num)
        return RankDataModel(players=players, count=count)

    async def get_first_rank_players_from_cache(
        self, rank_type: "GachaLogTypeEnum", query_type: "GachaLogQueryTypeEnum", desc: bool
    ) -> RankDataModel:
        desc_int = 1 if desc else 0
        key = f"{self.key}:{rank_type.value}:{query_type.value}:{desc_int}:total"
        data = await self.redis.get(key)
        if data:
            return RankDataModel.parse_raw(str(data, encoding="utf-8"))
        data = await self.get_first_rank_players_from_sql(rank_type, query_type, desc)
        await self.redis.set(key, data.json(by_alias=True), ex=self.expire)
        return data

    async def get_my_players_from_sql(
        self, user_id: int, rank_type: "GachaLogTypeEnum", query_type: "GachaLogQueryTypeEnum", desc: bool
    ) -> RankDataModel:
        players1 = await self.player_service.get_all_by_user_id(user_id)
        ranks = await self.gacha_log_rank_service.get_ranks_by_ids(rank_type, [player.player_id for player in players1])
        players = []
        real_desc = self.get_desc_type(query_type)
        if desc:
            real_desc = not real_desc
        for rank in ranks:
            num = await self.gacha_log_rank_service.get_rank_by_player_id_cache(
                rank_type, query_type, rank.player_id, desc=real_desc
            )
            if num is None:
                continue
            nickname = await self.get_nickname_from_uid(rank.player_id)
            players.append(self.mysql_to_model(rank, num + 1, nickname))
        players.sort(key=lambda x: x.num)
        return RankDataModel(players=players, count=len(players))

    async def get_my_players_from_cache(
        self, user_id: int, rank_type: "GachaLogTypeEnum", query_type: "GachaLogQueryTypeEnum", desc: bool
    ) -> RankDataModel:
        desc_int = 1 if desc else 0
        key = f"{self.key}:{rank_type.value}:{query_type.value}:{desc_int}:{user_id}"
        data = await self.redis.get(key)
        if data:
            return RankDataModel.parse_raw(str(data, encoding="utf-8"))
        data = await self.get_my_players_from_sql(user_id, rank_type, query_type, desc)
        await self.redis.set(key, data.json(by_alias=True), ex=self.expire2)
        return data

    @staticmethod
    def get_data_key_map_by_type(rank_type: "GachaLogTypeEnum"):
        data = {
            "总抽数": "score_1",
            "五星平均": "score_2",
        }
        if rank_type == GachaLogTypeEnum.CHARACTER:
            data.update(
                {
                    "UP平均": "score_3",
                    "小保底百分比": "score_4",
                }
            )
        return data

    def gen_button(self, user_id: int, desc: bool = False) -> List[List[InlineKeyboardButton]]:
        types = [self.TYPES[i : i + 2] for i in range(0, len(self.TYPES), 2)]
        if desc:
            now_bind, new_bind, now_int, new_int = "非酋榜", "欧皇榜", 1, 0
        else:
            now_bind, new_bind, now_int, new_int = "欧皇榜", "非酋榜", 0, 1
        data = [
            [
                InlineKeyboardButton(
                    idx[0],
                    callback_data=f"wish_log_rank|{user_id}|{idx[1].value}|{idx[2].value}|{now_int}",
                )
                for idx in id1
            ]
            for id1 in types
        ]
        page_button = [
            InlineKeyboardButton(f"当前是{now_bind}", callback_data=f"wish_log_rank_button|{user_id}|ignore"),
            InlineKeyboardButton(f"切换到{new_bind}", callback_data=f"wish_log_rank_button|{user_id}|{new_int}"),
        ]
        data.append(page_button)
        return data

    @handler.command("wish_log_rank", block=False)
    @handler.message(filters.Regex(r"^抽卡排行榜(.*)$"), block=False)
    async def wish_log_rank(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE"):
        user_id = await self.get_real_user_id(update)
        message = update.effective_message

        buttons = self.gen_button(user_id)
        if isinstance(self.wish_photo, str):
            photo = self.wish_photo
        else:
            photo = open("resources/img/wish.jpg", "rb")
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        reply_message = await message.reply_photo(
            photo=photo,
            caption="请选择你要查询的抽卡排行榜",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        if reply_message.photo:
            self.wish_photo = reply_message.photo[-1].file_id

    @handler.callback_query(pattern=r"^wish_log_rank\|", block=False)
    async def wish_log_rank_callback(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message

        async def get_wish_log_rank_callback(
            callback_query_data: str,
        ) -> Tuple[int, GachaLogTypeEnum, GachaLogQueryTypeEnum, bool]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _rank_type = GachaLogTypeEnum(int(_data[2]))
            _query_type = GachaLogQueryTypeEnum(_data[3])
            _desc = bool(int(_data[4]))
            logger.debug(
                "callback_query_data函数返回 user_id[%s] rank_type[%s] query_type[%s] desc[%s]",
                _user_id,
                _rank_type,
                _query_type,
                _desc,
            )
            return _user_id, _rank_type, _query_type, _desc

        try:
            user_id, rank_type, query_type, desc = await get_wish_log_rank_callback(callback_query.data)
        except IndexError:
            await callback_query.answer("按钮数据已过期，请重新获取。", show_alert=True)
            self.add_delete_message_job(message, delay=1)
            return
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        await self.render(update, context, user_id, rank_type, query_type, desc)

    async def get_render_data(
        self,
        user_id: int,
        rank_type: "GachaLogTypeEnum",
        query_type: "GachaLogQueryTypeEnum",
        desc: bool,
    ) -> Dict:
        my_data = await self.get_my_players_from_cache(user_id, rank_type, query_type, desc)
        list_data = await self.get_first_rank_players_from_cache(rank_type, query_type, desc)
        name_card = self.assets_service.namecard.navbar(0).as_uri()
        return {
            "data_list": [my_data, list_data],
            "count": list_data.count,
            "namecard": name_card,
            "pool_name": GachaLogRanks.ITEM_LIST_MAP_REV.get(rank_type),
            "data_key_map": self.get_data_key_map_by_type(rank_type),
            "main_key": query_type,
            "desc": desc,
        }

    async def render(
        self,
        update: "Update",
        _: "ContextTypes.DEFAULT_TYPE",
        user_id: int,
        rank_type: "GachaLogTypeEnum",
        query_type: "GachaLogQueryTypeEnum",
        desc: bool = False,
    ):
        callback_query = update.callback_query
        message = callback_query.message

        await message.reply_chat_action(ChatAction.TYPING)
        render_data = await self.get_render_data(user_id, rank_type, query_type, desc)
        try:
            await callback_query.answer(text="正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)
        except BadRequest:
            pass
        png_data = await self.template_service.render(
            "genshin/wish_log_rank/rank.jinja2",
            render_data,
            viewport={"width": 1040, "height": 500},
            full_page=True,
            query_selector=".container",
            file_type=FileType.PHOTO,
            ttl=1 * 60 * 60,
        )
        await png_data.edit_media(message)

    @handler.callback_query(pattern=r"^wish_log_rank_button\|", block=False)
    async def wish_log_rank_button_callback(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message

        async def get_wish_log_rank_button_callback(
            callback_query_data: str,
        ) -> Tuple[int, bool, bool]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _ignore = _data[2] == "ignore"
            _desc = False if _ignore else bool(int(_data[2]))
            logger.debug(
                "callback_query_data函数返回 user_id[%s] ignore[%s] desc[%s]",
                _user_id,
                _ignore,
                _desc,
            )
            return _user_id, _ignore, _desc

        try:
            user_id, ignore, desc = await get_wish_log_rank_button_callback(callback_query.data)
        except IndexError:
            await callback_query.answer("按钮数据已过期，请重新获取。", show_alert=True)
            self.add_delete_message_job(message, delay=1)
            return
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        if ignore:
            await callback_query.answer("无效按钮", show_alert=False)
            return
        buttons = self.gen_button(user_id, desc)
        await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer("已切换", show_alert=False)
