from aiofiles import open as async_open
from httpx import URL, AsyncClient

from utils.const import PROJECT_ROOT

GACHA_LOG_PAIMON_MOE_PATH = PROJECT_ROOT.joinpath("metadata/data/paimon_moe_zh.json")


async def update_paimon_moe_zh(overwrite: bool = True):
    if not overwrite and GACHA_LOG_PAIMON_MOE_PATH.exists():
        return
    host = URL("https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main/src/locales/items/zh.json")
    client = AsyncClient()
    text = (await client.get(host)).text
    async with async_open(GACHA_LOG_PAIMON_MOE_PATH, mode="w", encoding="utf-8") as file:
        await file.write(text)
