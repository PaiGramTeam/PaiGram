"""此文件用于储存 honey impact 中的部分基础数据"""

from __future__ import annotations

import ujson as json

from utils.const import PROJECT_ROOT
from utils.log import logger
from utils.typedefs import JSONType, StrOrInt

__all__ = [
    'HONEY_DATA',
    'AVATAR_DATA', 'WEAPON_DATA', 'MATERIAL_DATA', 'RELIQUARY_DATA',
]

data_dir = PROJECT_ROOT.joinpath('metadata/data/')


def _get_content(file_name: str) -> JSONType:
    path = data_dir.joinpath(file_name).with_suffix('.json')
    if not path.exists():
        logger.error(
            "暂未找到名为 \"{file_name}.json\" 的 metadata , "
            f"请先使用 [yellow bold]/refresh_metadata[/] 命令下载",
            extra={'markup': True}
        )
        return {}
    with open(path, encoding='utf-8') as file:
        return json.loads(file.read())


HONEY_DATA: dict[str, dict[StrOrInt, list[str]]] = _get_content('honey')

AVATAR_DATA: dict[str, dict[str, int | str | list[int]]] = _get_content('avatar')
WEAPON_DATA: dict[str, dict[str, int | str]] = _get_content('weapon')
MATERIAL_DATA: dict[str, dict[str, int | str]] = _get_content('material')
RELIQUARY_DATA: dict[str, dict[str, int | str | list[int] | dict[str, str]]] = _get_content('reliquary')
