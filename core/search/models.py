from abc import abstractmethod
from typing import Optional, List

from pydantic import BaseModel

__all__ = ["BaseEntry", "WeaponEntry", "WeaponsEntry", "StrategyEntry", "StrategyEntryList"]

from thefuzz import fuzz


class BaseEntry(BaseModel):
    """所有可搜索条目的基类。

    Base class for all searchable entries."""

    key: str  # 每个条目的Key必须唯一
    title: str
    description: str
    tags: Optional[List[str]] = []
    caption: Optional[str] = None
    parse_mode: Optional[str] = None
    photo_url: Optional[str] = None
    photo_file_id: Optional[str] = None

    @abstractmethod
    def compare_to_query(self, search_query: str) -> float:
        """返回一个数字 ∈[0,100] 描述搜索查询与此条目的相似程度。

        Gives a number ∈[0,100] describing how similar the search query is to this entry."""


class WeaponEntry(BaseEntry):
    def compare_to_query(self, search_query: str) -> float:
        score = 0.0
        if search_query == self.title:
            return 100
        if self.tags:
            if search_query in self.tags:
                return 99
            for tag in self.tags:
                _score = fuzz.partial_token_set_ratio(tag, search_query)
                if _score >= score:
                    score = _score
        if score >= 90:
            return score
        if self.description:
            _score = fuzz.partial_token_set_ratio(self.description, search_query)
            if _score >= score:
                return _score
        return score


class WeaponsEntry(BaseModel):
    data: Optional[List[WeaponEntry]]


class StrategyEntry(BaseEntry):
    def compare_to_query(self, search_query: str) -> float:
        score = 0.0
        if search_query == self.title:
            return 100
        if self.tags:
            if search_query in self.tags:
                return 99
            for tag in self.tags:
                _score = fuzz.partial_token_set_ratio(tag, search_query)
                if _score >= score:
                    score = _score
        return score


class StrategyEntryList(BaseModel):
    data: Optional[List[StrategyEntry]]
