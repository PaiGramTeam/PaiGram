import ujson as json
from aiofiles import open as async_open
from httpx import AsyncClient

from utils.const import AMBR_HOST, PROJECT_ROOT

__all__ = ['update_metadata_from_ambr']

client = AsyncClient()


async def update_metadata_from_ambr():
    targets = ['material', 'weapon', 'avatar', 'reliquary']
    for target in targets:
        url = AMBR_HOST.join(f"v2/chs/{target}")
        path = PROJECT_ROOT.joinpath(f'metadata/data/{target}.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        response = await client.get(url)
        data = json.loads(response.text)['data']['items']
        async with async_open(path, mode='w', encoding='utf-8') as file:
            await file.write(json.dumps(data, ensure_ascii=False))


async def main():
    await update_metadata_from_ambr()


def __main__():
    import asyncio
    import sys

    if sys.version_info >= (3, 8) and sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())


if __name__ == '__main__':
    __main__()
