import asyncio
import heapq
import itertools
import json
import os
import time
from pathlib import Path
from typing import Tuple, List, Optional, Dict

import aiofiles
from async_lru import alru_cache

from core.search.models import WeaponEntry, BaseEntry, WeaponsEntry
from utils.const import PROJECT_ROOT

ENTRY_DAYA_PATH = PROJECT_ROOT.joinpath("data", "entry")
ENTRY_DAYA_PATH.mkdir(parents=True, exist_ok=True)


class SearchServices:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.weapons: List[WeaponEntry] = []
        self.entry_data_path: Path = ENTRY_DAYA_PATH
        self.weapons_entry_data_path = self.entry_data_path / "weapon.json"
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

    async def save_entry(self) -> None:
        async with self._lock:
            if len(self.weapons) > 0:
                weapons = WeaponsEntry(data=self.weapons)
                await self.save_json(self.weapons_entry_data_path, weapons.json())

    async def add_entry(self, entry: BaseEntry, update: bool = False, ttl: int = 3600):
        async with self._lock:
            replace_time = self.replace_time.get(entry.key)
            if replace_time:
                if replace_time <= time.time() + ttl:
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

    async def remove_all_entry(self):
        async with self._lock:
            self.weapons = []
            if self.weapons_entry_data_path.exists():
                os.remove(self.weapons_entry_data_path)

    @staticmethod
    def _sort_key(entry: BaseEntry, search_query: str) -> float:
        return entry.compare_to_query(search_query)

    @alru_cache(maxsize=64)
    async def multi_search_combinations(self, search_queries: Tuple[str], results_per_query: int = 3):
        """多重搜索
        :param search_queries:
        :param results_per_query:
        :return: search results
        """
        results = {}
        effective_queries = list(dict.fromkeys(search_queries))
        for query in effective_queries:
            if res := await self.search(search_query=query, amount=results_per_query):
                results[query] = res

    @alru_cache(maxsize=64)
    async def search(self, search_query: Optional[str], amount: int = None) -> Optional[List[BaseEntry]]:
        # search_entries: Iterable[BaseEntry] = []
        async with self._lock:
            search_entries = itertools.chain(self.weapons)

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
