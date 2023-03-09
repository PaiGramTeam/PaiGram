import contextlib
from pathlib import Path
from typing import Tuple, Optional, List, Dict

import aiofiles
from genshin import Client, AuthkeyTimeout, InvalidAuthkey
from genshin.models import TransactionKind, BaseTransaction

from modules.pay_log.error import PayLogAuthkeyTimeout, PayLogInvalidAuthkey, PayLogNotFound
from modules.pay_log.models import PayLog as PayLogModel, BaseInfo
from utils.const import PROJECT_ROOT

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib

PAY_LOG_PATH = PROJECT_ROOT.joinpath("data", "apihelper", "pay_log")
PAY_LOG_PATH.mkdir(parents=True, exist_ok=True)


class PayLog:
    def __init__(self, pay_log_path: Path = PAY_LOG_PATH):
        self.pay_log_path = pay_log_path

    @staticmethod
    async def load_json(path):
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return jsonlib.loads(await f.read())

    @staticmethod
    async def save_json(path, data: PayLogModel):
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            return await f.write(data.json(ensure_ascii=False, indent=4))

    def get_file_path(
        self,
        user_id: str,
        uid: str,
        bak: bool = False,
    ) -> Path:
        """获取文件路径
        :param user_id: 用户 ID
        :param uid: UID
        :param bak: 是否为备份文件
        :return: 文件路径
        """
        return self.pay_log_path / f"{user_id}-{uid}.json{'.bak' if bak else ''}"

    async def load_history_info(
        self,
        user_id: str,
        uid: str,
        only_status: bool = False,
    ) -> Tuple[Optional[PayLogModel], bool]:
        """读取历史记录数据
        :param user_id: 用户id
        :param uid: 原神uid
        :param only_status: 是否只读取状态
        :return: 抽卡记录数据
        """
        file_path = self.get_file_path(user_id, uid)
        if only_status:
            return None, file_path.exists()
        if not file_path.exists():
            return PayLogModel(info=BaseInfo(uid=uid), list=[]), False
        try:
            return PayLogModel.parse_obj(await self.load_json(file_path)), True
        except jsonlib.JSONDecodeError:
            return PayLogModel(info=BaseInfo(uid=uid), list=[]), False

    async def remove_history_info(
        self,
        user_id: str,
        uid: str,
    ) -> bool:
        """删除历史记录数据
        :param user_id: 用户id
        :param uid: 原神uid
        :return: 是否删除成功
        """
        file_path = self.get_file_path(user_id, uid)
        file_bak_path = self.get_file_path(user_id, uid, bak=True)
        with contextlib.suppress(Exception):
            file_bak_path.unlink(missing_ok=True)
        if file_path.exists():
            try:
                file_path.unlink()
            except PermissionError:
                return False
            return True
        return False

    async def save_pay_log_info(self, user_id: str, uid: str, info: PayLogModel) -> None:
        """保存日志记录数据
        :param user_id: 用户id
        :param uid: 原神uid
        :param info: 记录数据
        """
        save_path = self.pay_log_path / f"{user_id}-{uid}.json"
        save_path_bak = self.pay_log_path / f"{user_id}-{uid}.json.bak"
        # 将旧数据备份一次
        with contextlib.suppress(PermissionError):
            if save_path.exists():
                if save_path_bak.exists():
                    save_path_bak.unlink()
                save_path.rename(save_path.parent / f"{save_path.name}.bak")
        # 写入数据
        await self.save_json(save_path, info)

    async def get_log_data(
        self,
        user_id: int,
        client: Client,
        authkey: str,
    ) -> int:
        """使用 authkey 获取历史记录数据，并合并旧数据
        :param user_id: 用户id
        :param client: genshin client
        :param authkey: authkey
        :return: 更新结果
        """
        new_num = 0
        pay_log, have_old = await self.load_history_info(str(user_id), str(client.uid))
        history_ids = [i.id for i in pay_log.list]
        try:
            async for data in client.transaction_log(TransactionKind.CRYSTAL, authkey=authkey):
                if data.id not in history_ids:
                    pay_log.list.append(data)
                    new_num += 1
        except AuthkeyTimeout as exc:
            raise PayLogAuthkeyTimeout from exc
        except InvalidAuthkey as exc:
            raise PayLogInvalidAuthkey from exc
        if new_num > 0 or have_old:
            pay_log.list.sort(key=lambda x: (x.time, x.id), reverse=True)
            pay_log.info.update_now()
            await self.save_pay_log_info(str(user_id), str(client.uid), pay_log)
        return new_num

    @staticmethod
    async def get_month_data(pay_log: PayLogModel, price_data: List[Dict]) -> Tuple[int, List[Dict]]:
        """获取月份数据
        :param pay_log: 日志数据
        :param price_data: 商品数据
        :return: 月份数据
        """
        all_amount: int = 0
        months: List[int] = []
        month_datas: List[Dict] = []
        last_month: Optional[Dict] = None
        month_data: List[Optional[BaseTransaction]] = []
        for i in pay_log.list:
            if i.amount <= 0:
                continue
            all_amount += i.amount
            if i.time.month not in months:
                months.append(i.time.month)
                if last_month:
                    last_month["amount"] = sum(i.amount for i in month_data)
                    month_data.clear()
                if len(months) <= 6:
                    last_month = {
                        "month": f"{i.time.month}月",
                        "amount": 0,
                    }
                    month_datas.append(last_month)
                else:
                    last_month = None
            for j in price_data:
                if i.amount in j["price"]:
                    j["count"] += 1
                    break
            month_data.append(i)
        if last_month:
            last_month["amount"] = sum(i.amount for i in month_data)
            month_data.clear()
        if not month_datas:
            raise PayLogNotFound
        return all_amount, month_datas

    async def get_analysis(self, user_id: int, client: Client):
        """获取分析数据
        :param user_id: 用户id
        :param client: genshin client
        :return: 分析数据
        """
        pay_log, status = await self.load_history_info(str(user_id), str(client.uid))
        if not status:
            raise PayLogNotFound
        # 单双倍结晶数
        price_data = [
            {
                "price": price,
                "count": 0,
            }
            for price in [[680], [300], [8080, 12960], [3880, 6560], [2240, 3960], [1090, 1960], [330, 600], [60, 120]]
        ]
        price_data_name = ["大月卡", "小月卡", "648", "328", "198", "98", "30", "6"]
        real_price = [68, 30, 648, 328, 198, 98, 30, 6]
        all_amount, month_datas = await PayLog.get_month_data(pay_log, price_data)
        month_data = sorted(month_datas, key=lambda k: k["amount"], reverse=True)
        all_pay = sum((price_data[i]["count"] * real_price[i]) for i in range(len(price_data)))
        datas = [
            {"value": f"￥{all_pay:.0f}", "name": "总消费"},
            {"value": all_amount, "name": "总结晶"},
            {"value": f"{month_data[0]['month']}", "name": "消费最多"},
            {
                "value": f"￥{month_data[0]['amount'] / 10:.0f}",
                "name": f"{month_data[0]['month']}消费",
            },
            *[
                {
                    "value": price_data[i]["count"] if i != 0 else "*",
                    "name": f"{price_data_name[i]}",
                }
                for i in range(len(price_data))
            ],
        ]
        pie_datas = [
            {
                "value": f"{price_data[i]['count'] * real_price[i]:.0f}",
                "name": f"{price_data_name[i]}",
            }
            for i in range(len(price_data))
            if price_data[i]["count"] > 0
        ]
        return {
            "uid": client.uid,
            "datas": datas,
            "bar_data": month_datas,
            "pie_data": pie_datas,
        }
