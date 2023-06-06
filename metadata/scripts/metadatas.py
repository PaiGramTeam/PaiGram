from contextlib import contextmanager
from typing import Iterator, Dict

import ujson as json
from aiofiles import open as async_open
from httpx import URL, AsyncClient, RemoteProtocolError, Response

from utils.const import AMBR_HOST, PROJECT_ROOT
from utils.log import logger

__all__ = ["update_metadata_from_ambr", "update_metadata_from_github", "RESOURCE_DEFAULT_PATH", "RESOURCE_FAST_URL"]
RESOURCE_REPO = "PaiGramTeam/PaiGram_Resources"
RESOURCE_BRANCH = "remote"
RESOURCE_ROOT = "Resources"
RESOURCE_DEFAULT_PATH = f"{RESOURCE_REPO}/{RESOURCE_BRANCH}/{RESOURCE_ROOT}/"
RESOURCE_FAST_URL = f"https://genshin-res.paimon.vip/{RESOURCE_ROOT}/"

client = AsyncClient()


async def fix_metadata_from_ambr(json_data: Dict[str, Dict], data_type: str):
    if data_type == "weapon":
        need_append_ids = [11304]
        need_attr = ["id", "rank", "type", "name", "icon", "route"]
        for wid in need_append_ids:
            url = AMBR_HOST.join(f"v2/chs/{data_type}/{wid}")
            response = await client.get(url)
            json_data_ = json.loads(response.text)["data"]
            json_data[str(json_data_["id"])] = {k: json_data_[k] for k in need_attr}


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
        await fix_metadata_from_ambr(json_data, target)
        async with async_open(path, mode="w", encoding="utf-8") as file:
            data = json.dumps(json_data, ensure_ascii=False)
            await file.write(data)
        result.append(json_data)
    return result


@contextmanager
async def stream_request(method, url) -> Iterator[Response]:
    async with client.stream(method=method, url=url) as response:
        yield response


# noinspection PyShadowingNames
async def update_metadata_from_github(overwrite: bool = True):
    path = PROJECT_ROOT.joinpath("metadata/data/namecard.json")
    if not overwrite and path.exists():
        return

    hosts = [
        URL(RESOURCE_FAST_URL),
        URL(f"https://raw.fastgit.org/{RESOURCE_DEFAULT_PATH}"),
        URL(f"https://raw.githubusercontent.com/{RESOURCE_DEFAULT_PATH}"),
    ]
    for num, host in enumerate(hosts):
        try:
            text_map_url = host.join("TextMap/TextMapCHS.json")
            material_url = host.join("ExcelBinOutput/MaterialExcelConfigData.json")

            material_json_data = []
            async with client.stream("GET", material_url) as response:
                started = False
                cell = []
                async for line in response.aiter_lines():
                    if line == "  {\n":
                        started = True
                        continue
                    if line in ["  },\n", "  }\n"]:
                        started = False
                        if any("MATERIAL_NAMECARD" in x for x in cell):
                            material_json_data.append(json.loads("{" + "".join(cell) + "}"))
                        cell = []
                        continue
                    if started:
                        if "materialType" in line and "MATERIAL_NAMECARD" not in line:
                            cell = []
                            started = False
                            continue
                        cell.append(line.strip(" \n"))

            string_ids = []
            for namecard_data in material_json_data:
                string_ids.append(str(namecard_data["nameTextMapHash"]))
                string_ids.append(str(namecard_data["descTextMapHash"]))

            text_map_json_data = {}
            async with client.stream("GET", text_map_url) as response:
                async for line in response.aiter_lines():
                    splits = line.split(":")
                    string_id = splits[0].strip(' "')
                    if string_id in string_ids:
                        text_map_json_data[string_id] = splits[1].strip('\n ,"')
                        string_ids.remove(string_id)
                    if not string_ids:
                        break

            data = {}
            for namecard_data in material_json_data:
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
        except RemoteProtocolError as exc:
            logger.warning("在从 %s 下载元数据的过程中遇到了错误: %s", host, str(exc))
            continue
        except Exception as exc:
            if num != len(hosts) - 1:
                logger.error("在从 %s 下载元数据的过程中遇到了错误: %s", host, str(exc))
                continue
            raise exc
