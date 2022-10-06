import ujson as json
from aiofiles import open as async_open
from httpx import AsyncClient, URL

from utils.const import AMBR_HOST, PROJECT_ROOT

__all__ = ['update_metadata_from_ambr', 'update_metadata_from_github']

client = AsyncClient()


async def update_metadata_from_ambr():
    result = []
    targets = ['material', 'weapon', 'avatar', 'reliquary']
    for target in targets:
        url = AMBR_HOST.join(f"v2/chs/{target}")
        path = PROJECT_ROOT.joinpath(f'metadata/data/{target}.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        response = await client.get(url)
        json_data = json.loads(response.text)['data']['items']
        async with async_open(path, mode='w', encoding='utf-8') as file:
            data = json.dumps(json_data, ensure_ascii=False)
            await file.write(data)
        result.append(json_data)
    return result


async def update_metadata_from_github():
    path = PROJECT_ROOT.joinpath(f'metadata/data/namecard.json')

    host = URL("https://raw.githubusercontent.com/Dimbreath/GenshinData/master/")
    # https://raw.githubusercontent.com/Dimbreath/GenshinData/master/TextMap/TextMapCHS.json
    material_url = host.join("ExcelBinOutput/MaterialExcelConfigData.json")
    text_map_url = host.join("TextMap/TextMapCHS.json")

    material_json_data = json.loads((await client.get(material_url)).text)
    text_map_json_data = json.loads((await client.get(text_map_url)).text)

    data = {}
    for namecard_data in filter(lambda x: x['icon'].startswith('UI_NameCardIcon'), material_json_data):
        name = text_map_json_data[str(namecard_data['nameTextMapHash'])]
        icon = namecard_data['icon']
        navbar = namecard_data['picPath'][0]
        banner = namecard_data['picPath'][1]
        rank = namecard_data['rankLevel']
        description = text_map_json_data[str(namecard_data['descTextMapHash'])].replace('\\n', '\n')
        data.update({
            str(namecard_data['id']): {
                "id": namecard_data['id'],
                "name": name,
                "rank": rank,
                "icon": icon,
                "navbar": navbar,
                "profile": banner,
                "description": description,
            }
        })
    async with async_open(path, mode='w', encoding='utf-8') as file:
        data = json.dumps(data, ensure_ascii=False)
        await file.write(data)
    return data


async def main():
    await update_metadata_from_ambr()
    await update_metadata_from_github()


def __main__():
    import asyncio
    import sys

    if sys.version_info >= (3, 8) and sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())


if __name__ == '__main__':
    __main__()
