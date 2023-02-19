from typing import List

from pydantic import BaseModel


class Label(BaseModel):
    id: int
    name: str
    depth: int


class LabelTree(Label):
    children: List[Label]


class Point(BaseModel):
    id: int
    label_id: int


class ListData(BaseModel):
    point_list: List[Point]
    label_list: List[Label]
