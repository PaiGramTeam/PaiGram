import asyncio
import hashlib
import hmac
import uuid

from genshin import Client
from httpx import AsyncClient
from .authclient import AuthClient
from ...models.genshin.recharge import GoodsList, Goods, Order


class RechargeClient:
    GOODS_URL = f"https://{AuthClient.HK4E_SDK_HOST}/hk4e_cn/mdk/shopwindow/shopwindow/fetchGoods"
    CREATE_ORDER_URL = f"https://{AuthClient.HK4E_SDK_HOST}/hk4e_cn/mdk/atropos/api/createOrder"
    CHECK_ORDER_URL = f"https://{AuthClient.HK4E_SDK_HOST}/hk4e_cn/mdk/atropos/api/checkOrder"
    HEADER = _HEADER = {
        'x-rpc-app_version': "2.11.1",
        'User-Agent': (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) miHoYoBBS/2.11.1'
        ),
        'x-rpc-client_type': '4',
        'Referer': 'https://webstatic.mihoyo.com/',
        'Origin': 'https://webstatic.mihoyo.com',
    }

    def __init__(self):
        self.client = AsyncClient()

    async def fetch_goods(self) -> GoodsList:
        data = {
            "released_flag": True,
            "game": "hk4e_cn",
            "region": "cn_gf01",
            "uid": "1",
            "account": "1",
        }
        goods_list = await self.client.post(
            self.GOODS_URL,
            json=data,
        )
        return GoodsList(**goods_list.json()["data"])

    async def create_order(self, client: Client, account_id: int, goods: Goods) -> Order:
        device_id = str(uuid.uuid4())
        order = {
            "account": str(account_id),
            "region": "cn_gf01",
            "uid": client.uid,
            "delivery_url": "",
            "device": device_id,
            "channel_id": 1,
            "client_ip": "",
            "client_type": 4,
            "game": "hk4e_cn",
            "amount": goods.price,
            "goods_num": 1,
            "goods_id": goods.goods_id,
            "goods_title": goods.title,
            "price_tier": goods.tier_id,
            "currency": "CNY",
            "pay_plat": "alipay",
        }
        data = {"order": order, "sign": self.gen_payment_sign(order)}
        headers = self.HEADER.copy()
        headers["x-rpc-device_id"] = device_id
        order = await client.cookie_manager.request(
            self.CREATE_ORDER_URL,
            method="POST",
            headers=headers,
            json=data,
        )
        return Order(**order)

    async def check_order(self, client: Client, order: Order) -> bool:
        data = {
            "order_no": order.order_no,
            "game": "hk4e_cn",
            "region": "cn_gf01",
            "uid": str(client.uid),
        }
        for _ in range(20):
            await asyncio.sleep(5)
            order = await client.cookie_manager.request(
                self.CHECK_ORDER_URL,
                method='GET',
                headers=self.HEADER.copy(),
                params=data,
            )
            status = order.get("status", 1)
            if status == 900:
                return True
        return False

    @staticmethod
    def generate_qrcode(order: Order) -> bytes:
        return AuthClient.generate_qrcode(order.url)

    @staticmethod
    def sha256(data, key):
        key = key.encode("utf-8")
        message = data.encode("utf-8")
        sign = hmac.new(key, message, digestmod=hashlib.sha256).digest()
        return sign.hex()

    @staticmethod
    def gen_payment_sign(data):
        data = dict(sorted(data.items(), key=lambda x: x[0]))
        value = "".join([str(i) for i in data.values()])
        return RechargeClient.sha256(value, "6bdc3982c25f3f3c38668a32d287d16b")
