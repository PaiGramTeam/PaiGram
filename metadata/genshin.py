"""此文件用于储存 honey impact 中的部分基础数据"""

from __future__ import annotations

import functools
from typing import Any, Generic, ItemsView, Iterator, KeysView, TypeVar

import ujson as json

from utils.const import PROJECT_ROOT
from utils.log import logger
from utils.typedefs import StrOrInt

__all__ = [
    "HONEY_DATA",
    "AVATAR_DATA",
    "WEAPON_DATA",
    "MATERIAL_DATA",
    "ARTIFACT_DATA",
    "NAMECARD_DATA",
    "honey_id_to_game_id",
    "Data",
]

K = TypeVar("K")
V = TypeVar("V")

data_dir = PROJECT_ROOT.joinpath("metadata/data/")
data_dir.mkdir(parents=True, exist_ok=True)

_cache = {}


class Data(dict, Generic[K, V]):
    _dict: dict[K, V]
    _file_name: str

    @property
    def data(self) -> dict[K, V]:
        if (result := _cache.get(self._file_name)) not in [None, {}]:
            self._dict = result
        else:
            path = data_dir.joinpath(self._file_name).with_suffix(".json")
            if not path.exists():
                logger.error(
                    f'暂未找到名为 "{self._file_name}.json" 的 metadata , ' "请先使用 [yellow bold]/refresh_metadata[/] 命令下载",
                    extra={"markup": True},
                )
                self._dict = {}
            with open(path, encoding="utf-8") as file:
                self._dict = json.load(file)
            _cache.update({self._file_name: self._dict})
        return self._dict

    def __init__(self, file_name: str):
        self._file_name = file_name
        self._dict = {}
        super(Data, self).__init__()

    def get(self, key: K, value: Any = None) -> V | None:
        return self.data.get(key, value)

    def __getitem__(self, key: K) -> V:
        return self.data.__getitem__(key)

    def __setitem__(self, key: K, value: V) -> None:
        return self.data.__setitem__(key, value)

    def __delitem__(self, value: V) -> None:
        self.data.__delitem__(value)

    def __iter__(self) -> Iterator[K]:
        return self.data.__iter__()

    def keys(self) -> KeysView[K, V]:
        return self.data.keys()

    def items(self) -> ItemsView[K, V]:
        return self.data.items()


HONEY_DATA: dict[str, dict[StrOrInt, list[str | int]]] = Data("honey")

AVATAR_DATA: dict[str, dict[str, int | str | list[int]]] = Data("avatar")
WEAPON_DATA: dict[str, dict[str, int | str]] = Data("weapon")
MATERIAL_DATA: dict[str, dict[str, int | str]] = Data("material")
ARTIFACT_DATA: dict[str, dict[str, int | str | list[int] | dict[str, str]]] = Data("reliquary")
NAMECARD_DATA: dict[str, dict[str, int | str]] = Data("namecard")


@functools.lru_cache()
def honey_id_to_game_id(honey_id: str, item_type: str) -> str | None:
    return next((key for key, value in HONEY_DATA[item_type].items() if value[0] == honey_id), None)
