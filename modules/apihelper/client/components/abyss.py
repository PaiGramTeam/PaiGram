import time
from typing import List

import httpx
from pydantic import parse_obj_as

from ...models.genshin.abyss import TeamRateResult, TeamRate

__all__ = ("AbyssTeam",)


class AbyssTeam:
    TEAM_RATE_API = "https://www.youchuang.fun/gamerole/formationRate"
    HEADERS = {
        "Host": "www.youchuang.fun",
        "Referer": "https://servicewechat.com/wxce4dbe0cb0f764b3/91/page-frame.html",
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 15_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Mobile/15E148 MicroMessenger/8.0.20(0x1800142f) NetType/WIFI Language/zh_CN",
        "content-type": "application/json",
    }
    VERSION = "3.2"

    def __init__(self):
        self.client = httpx.AsyncClient(headers=self.HEADERS)
        self.time = 0
        self.data = None
        self.ttl = 10 * 60

    async def get_data(self) -> TeamRateResult:
        if self.data is None or self.time + self.ttl < time.time():
            data_up = await self.client.post(self.TEAM_RATE_API, json={"version": self.VERSION, "layer": 1})
            data_up_json = data_up.json()["result"]
            data_down = await self.client.post(self.TEAM_RATE_API, json={"version": self.VERSION, "layer": 2})
            data_down_json = data_down.json()["result"]
            self.data = TeamRateResult(
                version=self.VERSION,
                rate_list_up=parse_obj_as(List[TeamRate], data_up_json["rateList"]),
                rate_list_down=parse_obj_as(List[TeamRate], data_down_json["rateList"]),
                user_count=data_up_json["userCount"],
            )
            self.time = time.time()
        return self.data.copy(deep=True)

    async def close(self):
        await self.client.aclose()
