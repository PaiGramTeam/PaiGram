from utils.const import PROJECT_ROOT
from aiofiles import open as async_open
from httpx import AsyncClient, URL


async def update_paimon_moe_zh(overwrite: bool = True):
    path = PROJECT_ROOT.joinpath("metadata/data/paimon_moe_zh.json")
    if not overwrite and path.exists():
        return
    host = URL("https://raw.fastgit.org/MadeBaruna/paimon-moe/main/src/locales/items/zh.json")
    client = AsyncClient()
    text = (await client.get(host)).text
    async with async_open(path, mode="w", encoding="utf-8") as file:
        await file.write(text)
