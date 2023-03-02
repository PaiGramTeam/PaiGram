import json
from pathlib import Path
from typing import Dict, Union

from httpx import AsyncClient, HTTPError

from modules.apihelper.models.genshin.map import LabelTree, ListData
from utils.const import PROJECT_ROOT

MAP_PATH = PROJECT_ROOT.joinpath("data", "apihelper", "map")
MAP_PATH.mkdir(parents=True, exist_ok=True)


class MapException(Exception):
    """提瓦特地图异常"""

    def __init__(self, message: str):
        self.message = message


class MapHelper:
    """提瓦特大地图"""

    MAP_API_URL = "https://map.minigg.cn/map/get_map"
    LABEL_URL = "https://api-static.mihoyo.com/common/blackboard/ys_obc/v1/map/label/tree?app_sn=ys_obc"
    COUNT_URL = "https://api-static.mihoyo.com/common/blackboard/ys_obc/v1/map/point/list"
    COUNT_PARAMS = {"app_sn": "ys_obc", "map_id": "2"}
    MAP_ID_LIST = [
        "2",
        "7",
        "9",
    ]
    MAP_NAME_LIST = [
        "提瓦特大陆",
        "渊下宫",
        "层岩巨渊·地下矿区",
    ]

    def __init__(self):
        self.client = AsyncClient()
        self.query_map_path = MAP_PATH / "query_map.json"
        self.label_count_path = MAP_PATH / "label_count.json"
        self.query_map: Dict[str, str] = {}
        self.label_count: Dict[str, Dict[str, int]] = {}
        self.load(self.query_map, self.query_map_path)
        self.load(self.label_count, self.label_count_path)

    @staticmethod
    def load(data: Dict, path: Path) -> None:
        """加载文件"""
        if not path.exists():
            return
        data.clear()
        with open(path, "r", encoding="utf-8") as f:
            data.update(json.load(f))

    def save(self, data: Dict, path: Path) -> None:
        """保存查询映射"""
        if path not in [self.query_map_path, self.label_count_path]:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    async def refresh_query_map(self) -> None:
        """刷新查询映射"""
        data = {}
        label_data = await self.client.get(self.LABEL_URL)
        for label_tree_source in label_data.json().get("data", {}).get("tree", []):
            label_tree = LabelTree(**label_tree_source)
            for child in label_tree.children:
                data[child.name] = str(child.id)
        self.query_map = data
        self.save(data, self.query_map_path)

    async def refresh_label_count(self) -> None:
        """刷新标签数量"""
        data = self.label_count
        for map_id in self.MAP_ID_LIST:
            data[map_id] = {}
            params = self.COUNT_PARAMS.copy()
            params["map_id"] = map_id
            count_data = await self.client.get(self.COUNT_URL, params=params)
            list_data = ListData(**count_data.json().get("data", {}))
            for label in list_data.label_list:
                if label.depth == 2:
                    data[map_id][label.name] = len([i for i in list_data.point_list if i.label_id == label.id])
        self.save(data, self.label_count_path)

    def get_label_count(self, map_id: Union[str, int], label_name: str) -> int:
        """获取标签数量"""
        return self.label_count.get(str(map_id), {}).get(label_name, 0)

    async def get_map(self, map_id: Union[str, int], name: str) -> bytes:
        """获取资源图片"""
        try:
            req = await self.client.get(
                self.MAP_API_URL,
                params={
                    "resource_name": name,
                    "map_id": str(map_id),
                    "is_cluster": False,
                },
                timeout=60,
            )
        except HTTPError as e:
            raise MapException("请求超时，请稍后再试") from e
        if req.headers.get("content-type") == "image/jpeg":
            return req.content
        if req.headers.get("content-type") == "application/json":
            raise MapException(req.json().get("message", "遇到未知错误，请稍后再试"))
        raise MapException("遇到未知错误，请稍后再试")
