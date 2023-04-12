from base64 import b64decode as parse_token
from contextlib import contextmanager
from typing import Iterator

import ujson as json
from aiofiles import open as async_open
from httpx import URL, AsyncClient, RemoteProtocolError, Response

from utils.const import AMBR_HOST, PROJECT_ROOT
from utils.log import logger

__all__ = ["update_metadata_from_ambr", "update_metadata_from_github", "make_github_fast", "RESOURCE_DEFAULT_PATH"]
GENSHIN_PY_DATA_REPO = parse_token("aHR0cHM6Ly9naXRsYWIuY29tL0RpbWJyZWF0aC9nYW1lZGF0YS8tL3Jhdy9tYXN0ZXIv").decode()
RESOURCE_REPO = "PaiGramTeam/PaiGram_Resources"
RESOURCE_BRANCH = "remote"
RESOURCE_ROOT = "Resources"
RESOURCE_DEFAULT_PATH = f"{RESOURCE_REPO}/{RESOURCE_BRANCH}/{RESOURCE_ROOT}/"

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
        URL(f"https://ghproxy.net/https://raw.githubusercontent.com/{RESOURCE_DEFAULT_PATH}"),
        URL(f"https://github.91chi.fun/https://raw.githubusercontent.com/{RESOURCE_DEFAULT_PATH}"),
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
                    if (string_id := (splits := line.split(":"))[0].strip(' "')) in string_ids:
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


def make_github_fast(url: str) -> str:
    url = url.replace("Dimbreath/GenshinData/master/", RESOURCE_DEFAULT_PATH)
    return url.replace(
        GENSHIN_PY_DATA_REPO,
        f"https://raw.githubusercontent.com/{RESOURCE_DEFAULT_PATH}",
    )
