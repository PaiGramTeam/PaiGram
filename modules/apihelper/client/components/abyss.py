import time
from typing import List, Dict

import httpx

__all__ = ("AbyssTeam",)


class AbyssTeam:
    TEAM_RATE_API = "https://homa.snapgenshin.com/Statistics/Team/Combination"
    HEADERS = {
        "Host": "homa.snapgenshin.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Safari/537.36 PaiGram/4.0",
        "content-type": "application/json",
    }

    # This should not be there
    VERSION = "3.5"

    def __init__(self):
        self.client = httpx.AsyncClient(headers=self.HEADERS)
        self.time = 0
        self.data = None
        self.ttl = 10 * 60

    async def get_data(self) -> List[Dict[str, Dict]]:
        if self.data is None or self.time + self.ttl < time.time():
            data = await self.client.get(self.TEAM_RATE_API)
            data_json = data.json()["data"]
            self.data = data_json
            self.time = time.time()
        return self.data.copy()

    async def close(self):
        await self.client.aclose()
