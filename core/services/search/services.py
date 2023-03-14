import asyncio
import heapq
import itertools
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiofiles
from async_lru import alru_cache

from core.base_service import BaseService
from core.services.search.models import BaseEntry, StrategyEntry, StrategyEntryList, WeaponEntry, WeaponsEntry
from utils.const import PROJECT_ROOT

__all__ = ("SearchServices",)

ENTRY_DAYA_PATH = PROJECT_ROOT.joinpath("data", "entry")
ENTRY_DAYA_PATH.mkdir(parents=True, exist_ok=True)


class SearchServices(BaseService):
    def __init__(self):
        self._lock = asyncio.Lock()  # 访问和修改操作成员变量必须加锁操作
        self.weapons: List[WeaponEntry] = []
        self.strategy: List[StrategyEntry] = []
        self.entry_data_path: Path = ENTRY_DAYA_PATH
        self.weapons_entry_data_path = self.entry_data_path / "weapon.json"
        self.strategy_entry_data_path = self.entry_data_path / "strategy.json"
        self.replace_time: Dict[str, float] = {}

    @staticmethod
    async def load_json(path):
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return json.loads(await f.read())

    @staticmethod
    async def save_json(path, data):
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(data)

    async def load_data(self):
        async with self._lock:
            if self.weapons_entry_data_path.exists():
                weapon_json = await self.load_json(self.weapons_entry_data_path)
                weapons = WeaponsEntry.parse_obj(weapon_json)
                for weapon in weapons.data:
                    self.weapons.append(weapon.copy())
            if self.strategy_entry_data_path.exists():
                strategy_json = await self.load_json(self.strategy_entry_data_path)
                strategy = StrategyEntryList.parse_obj(strategy_json)
                for strategy in strategy.data:
                    self.strategy.append(strategy.copy())

    async def save_entry(self) -> None:
        """保存条目
        :return: None
        """
        async with self._lock:
            if len(self.weapons) > 0:
                weapons = WeaponsEntry(data=self.weapons)
                await self.save_json(self.weapons_entry_data_path, weapons.json())
            if len(self.strategy) > 0:
                strategy = StrategyEntryList(data=self.strategy)
                await self.save_json(self.strategy_entry_data_path, strategy.json())

    async def add_entry(self, entry: BaseEntry, update: bool = False, ttl: int = 3600):
        """添加条目
        :param entry: 条目数据
        :param update: 如果条目存在是否覆盖
        :param ttl: 条目存在时需要多久时间覆盖
        :return: None
        """
        async with self._lock:
            replace_time = self.replace_time.get(entry.key)
            if replace_time and replace_time <= time.time() + ttl:
                return
            if isinstance(entry, WeaponEntry):
                for index, value in enumerate(self.weapons):
                    if value.key == entry.key:
                        if update:
                            self.replace_time[entry.key] = time.time()
                            self.weapons[index] = entry
                        break
                else:
                    self.weapons.append(entry)
            elif isinstance(entry, StrategyEntry):
                for index, value in enumerate(self.strategy):
                    if value.key == entry.key:
                        if update:
                            self.replace_time[entry.key] = time.time()
                            self.strategy[index] = entry
                        break
                else:
                    self.strategy.append(entry)

    async def remove_all_entry(self):
        """移除全部条目
        :return: None
        """
        async with self._lock:
            self.weapons = []
            if self.weapons_entry_data_path.exists():
                os.remove(self.weapons_entry_data_path)
            self.strategy = []
            if self.strategy_entry_data_path.exists():
                os.remove(self.strategy_entry_data_path)

    @staticmethod
    def _sort_key(entry: BaseEntry, search_query: str) -> float:
        return entry.compare_to_query(search_query)

    @alru_cache(maxsize=64)
    async def multi_search_combinations(self, search_queries: Tuple[str], results_per_query: int = 3):
        """多个关键词搜索
        :param search_queries: 搜索文本
        :param results_per_query: 约定返回的数目
        :return: 搜索结果
        """
        results = {}
        effective_queries = list(dict.fromkeys(search_queries))
        for query in effective_queries:
            if res := await self.search(search_query=query, amount=results_per_query):
                results[query] = res

    @alru_cache(maxsize=64)
    async def search(self, search_query: Optional[str], amount: int = None) -> Optional[List[BaseEntry]]:
        """在所有可用条目中搜索适当的结果
        :param search_query: 搜索文本
        :param amount: 约定返回的数目
        :return: 搜索结果
        """
        # search_entries: Iterable[BaseEntry] = []
        async with self._lock:
            search_entries = itertools.chain(self.weapons, self.strategy)

            if not search_query:
                return search_entries if isinstance(search_entries, list) else list(search_entries)

            if not amount:
                return sorted(
                    search_entries,
                    key=lambda entry: self._sort_key(entry, search_query),  # type: ignore
                    reverse=True,
                )
            return heapq.nlargest(
                amount,
                search_entries,
                key=lambda entry: self._sort_key(entry, search_query),  # type: ignore[arg-type]
            )
