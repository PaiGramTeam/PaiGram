from typing import List

from pydantic import BaseModel


class Goods(BaseModel):
    goods_id: str
    goods_name: str
    price: str
    goods_unit: str
    tier_id: str

    @property
    def real_price(self) -> int:
        return int(self.price) // 100

    @property
    def title(self) -> str:
        return f"{self.goods_name}×{str(self.goods_unit)}" if int(self.goods_unit) > 0 else self.goods_name


class GoodsList(BaseModel):
    goods_list: List[Goods]


class Order(BaseModel):
    order_no: str
    encode_order: str
    amount: str

    @property
    def real_amount(self) -> int:
        return int(self.amount) // 100

    @property
    def url(self) -> str:
        return self.encode_order
