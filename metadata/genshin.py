"""此文件用于储存 honey impact 中的部分基础数据"""

from __future__ import annotations

import ujson as json

from utils.const import PROJECT_ROOT
from utils.log import logger
from utils.typedefs import JSONType, StrOrInt

__all__ = [
    'HONEY_DATA',
    'AVATAR_DATA', 'WEAPON_DATA', 'MATERIAL_DATA', 'ARTIFACT_DATA', 'NAMECARD_DATA',
    'honey_id_to_game_id'
]

data_dir = PROJECT_ROOT.joinpath('metadata/data/')
data_dir.mkdir(parents=True, exist_ok=True)


def _get_content(file_name: str) -> JSONType:
    path = data_dir.joinpath(file_name).with_suffix('.json')
    if not path.exists():
        logger.error(
            f"暂未找到名为 \"{file_name}.json\" 的 metadata , 请先使用 [yellow bold]/refresh_metadata[/] 命令下载",
            extra={'markup': True}
        )
        return {}
    with open(path, encoding='utf-8') as file:
        return json.load(file)


HONEY_DATA: dict[str, dict[StrOrInt, list[str | int]]] = _get_content('honey')

AVATAR_DATA: dict[str, dict[str, int | str | list[int]]] = _get_content('avatar')
WEAPON_DATA: dict[str, dict[str, int | str]] = _get_content('weapon')
MATERIAL_DATA: dict[str, dict[str, int | str]] = _get_content('material')
ARTIFACT_DATA: dict[str, dict[str, int | str | list[int] | dict[str, str]]] = _get_content('reliquary')
NAMECARD_DATA: dict[str, dict[str, int | str]] = _get_content('namecard')


def honey_id_to_game_id(honey_id: str, item_type: str) -> str | None:
    return next((key for key, value in HONEY_DATA[item_type].items() if value[0] == honey_id), None)
