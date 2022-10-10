import ujson as json
from aiofiles import open as async_open
from httpx import AsyncClient, URL

from utils.const import AMBR_HOST, PROJECT_ROOT

__all__ = ["update_metadata_from_ambr", "update_metadata_from_github"]

client = AsyncClient()


async def update_metadata_from_ambr(overwrite: bool = True):
    result = []
    targets = ["material", "weapon", "avatar", "reliquary"]
    for target in targets:
        path = PROJECT_ROOT.joinpath(f"metadata/data/{target}.json")
        if not overwrite and path.exists():
            continue
        url = AMBR_HOST.join(f"v2/chs/{target}")
        path.parent.mkdir(parents=True, exist_ok=True)
        response = await client.get(url)
        json_data = json.loads(response.text)["data"]["items"]
        async with async_open(path, mode="w", encoding="utf-8") as file:
            data = json.dumps(json_data, ensure_ascii=False)
            await file.write(data)
        result.append(json_data)
    return result


async def update_metadata_from_github(overwrite: bool = True):
    path = PROJECT_ROOT.joinpath("metadata/data/namecard.json")
    if not overwrite and path.exists():
        return

    host = URL("https://raw.fastgit.org/Dimbreath/GenshinData/master/")

    text_map_url = host.join("TextMap/TextMapCHS.json")
    material_url = host.join("ExcelBinOutput/MaterialExcelConfigData.json")

    text_map_json_data = json.loads((await client.get(text_map_url)).text)
    material_json_data = json.loads((await client.get(material_url)).text)

    data = {}
    for namecard_data in filter(lambda x: x.get("materialType", None) == "MATERIAL_NAMECARD", material_json_data):
        name = text_map_json_data[str(namecard_data["nameTextMapHash"])]
        icon = namecard_data["icon"]
        navbar = namecard_data["picPath"][0]
        banner = namecard_data["picPath"][1]
        rank = namecard_data["rankLevel"]
        description = text_map_json_data[str(namecard_data["descTextMapHash"])].replace("\\n", "\n")
        data.update(
            {
                str(namecard_data["id"]): {
                    "id": namecard_data["id"],
                    "name": name,
                    "rank": rank,
                    "icon": icon,
                    "navbar": navbar,
                    "profile": banner,
                    "description": description,
                }
            }
        )
    async with async_open(path, mode="w", encoding="utf-8") as file:
        data = json.dumps(data, ensure_ascii=False)
        await file.write(data)
    return data
