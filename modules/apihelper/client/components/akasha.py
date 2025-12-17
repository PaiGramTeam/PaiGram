from types import TracebackType
from typing import Optional, Type, List
from urllib.parse import unquote

import httpx

from gram_core.basemodel import Settings
from modules.apihelper.models.genshin.akasha import (
    AkashaRank,
    AkashaLeaderboardCategory,
    AkashaLeaderboard,
    AkashaSubStat,
    AkashaArtifact,
)

BASE_URL = "https://akasha.cv/api"
MAIN_API = BASE_URL + "/filters/accounts/"
RANK_API = BASE_URL + "/getCalculationsForUser/"
DATA_API = BASE_URL + "/user/"
REFRESH_API = BASE_URL + "/user/refresh/"
LEADERBOARD_API = BASE_URL + "/leaderboards"
LEADERBOARD_CATEGORY_API = BASE_URL + "/v2/leaderboards/categories"
ARTIFACTS_API = BASE_URL + "/artifacts"


class AkashaConfig(Settings):
    akasha_api_agent: str = ""


class Akasha:
    SUB_STAT_MAP = {
        AkashaSubStat.CRR: "critValue",
        AkashaSubStat.ATK: "substats.ATK%",
        AkashaSubStat.HP: "substats.HP%",
        AkashaSubStat.DEF: "substats.DEF%",
        AkashaSubStat.ATKF: "substats.Flat ATK",
        AkashaSubStat.HPF: "substats.Flat HP",
        AkashaSubStat.DEFF: "substats.Flat DEF",
        AkashaSubStat.EM: "substats.Elemental Mastery",
        AkashaSubStat.ER: "substats.Energy Recharge",
        AkashaSubStat.CR: "substats.Crit RATE",
        AkashaSubStat.CD: "substats.Crit DMG",
    }
    SUB_STAT_NAME_MAP = {
        "Flat ATK": "攻击力",
        "Flat HP": "血量",
        "Flat DEF": "防御力",
        "ATK%": "百分比攻击力",
        "HP%": "百分比血量",
        "DEF%": "百分比防御",
        "Elemental Mastery": "元素精通",
        "Energy Recharge": "元素充能效率",
        "Crit RATE": "暴击率",
        "Crit DMG": "暴击伤害",
        "Cryo DMG Bonus": "冰元素伤害加成",
        "Pyro DMG Bonus": "火元素伤害加成",
        "Hydro DMG Bonus": "水元素伤害加成",
        "Electro DMG Bonus": "雷元素伤害加成",
        "Anemo DMG Bonus": "风元素伤害加成",
        "Geo DMG Bonus": "岩元素伤害加成",
        "Dendro DMG Bonus": "草元素伤害加成",
        "Healing Bonus": "治疗加成",
        "Physical Bonus": "物理伤害加成",
    }

    def __init__(self):
        self.config = AkashaConfig()
        headers = {
            "User-Agent": self.config.akasha_api_agent,
        }
        self.client = httpx.AsyncClient(timeout=60, headers=headers)
        self.session_id = None

    async def get_session_id(self) -> Optional[str]:
        if self.session_id is None:
            resp = await self.client.get(MAIN_API)
            sid = resp.cookies.get("connect.sid", "")
            sid = unquote(str(sid))
            self.session_id = sid.split(".")[0].split(":")[-1]
        return self.session_id

    async def refresh_user_data(self, uid: int) -> None:
        session_id = await self.get_session_id()
        params = {"sessionID": session_id}
        await self.client.get(DATA_API + str(uid), params=params)
        await self.client.get(REFRESH_API + str(uid), params=params)

    async def get_rank_data(self, uid: int) -> List[AkashaRank]:
        await self.refresh_user_data(uid)
        try:
            resp = await self.client.get(RANK_API + str(uid))
            data = resp.json()["data"]
        except KeyError:
            return []
        return [AkashaRank(**i) for i in data]

    async def get_leaderboard_categories(self, character_id: int) -> List[AkashaLeaderboardCategory]:
        params = {"characterId": character_id}
        try:
            resp = await self.client.get(LEADERBOARD_CATEGORY_API, params=params)
            data = resp.json()["data"]
        except KeyError:
            return []
        return [AkashaLeaderboardCategory(**i) for i in data]

    async def get_leaderboard(self, calculation_id: str, uid: int = None) -> List[AkashaLeaderboard]:
        params = {
            "sort": "calculation.result",
            "p": "",
            "calculationId": calculation_id,
            "order": -1,
            "size": 20,
            "page": 1,
            "filter": "",
            "uids": "",
            "fromId": "",
        }
        if uid:
            params["uids"] = f"[uid]{uid}"
        try:
            resp = await self.client.get(LEADERBOARD_API, params=params)
            data = resp.json()["data"]
        except KeyError:
            return []
        return [AkashaLeaderboard(**i) for i in data]

    async def get_artifacts_list(self, sort_by: AkashaSubStat = AkashaSubStat.CRR) -> List[AkashaArtifact]:
        params = {
            "sort": self.SUB_STAT_MAP[sort_by],
            "p": "",
        }
        try:
            resp = await self.client.get(ARTIFACTS_API, params=params)
            data = resp.json()["data"]
        except KeyError:
            return []
        return [AkashaArtifact(**i) for i in data]

    async def __aenter__(self):
        return self

    async def __aexit__(
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ):
        if self.client.is_closed:
            return
        await self.client.aclose()
