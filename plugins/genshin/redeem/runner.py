import asyncio
from dataclasses import dataclass
from queue import PriorityQueue
from typing import Coroutine, Any, Optional, List, TYPE_CHECKING, Union

from simnet.errors import RegionNotSupported, RedemptionInvalid, RedemptionClaimed, RedemptionCooldown
from telegram import Message

from gram_core.basemodel import RegionEnum
from plugins.tools.genshin import GenshinHelper

if TYPE_CHECKING:
    from simnet import GenshinClient


@dataclass
class RedeemResult:
    user_id: int
    code: str
    message: Optional[Message] = None
    error: Optional[str] = None
    uid: Optional[int] = None
    count: Optional[List[int]] = None


class RedeemRunnerTask:
    def __init__(self, task: Coroutine[Any, Any, None]):
        self.task = task

    def __lt__(self, other: "RedeemRunnerTask") -> bool:
        return False

    async def run(self) -> None:
        await self.task


class RedeemQueueFull(Exception):
    pass


class RedeemRunner:
    def __init__(self, genshin_helper: GenshinHelper):
        self.gcsim_version: Optional[str] = None
        self.sema = asyncio.BoundedSemaphore(1)
        self.queue_size = 21
        self.queue: PriorityQueue[List[Union[int, RedeemRunnerTask]]] = PriorityQueue(maxsize=self.queue_size)
        self.genshin_helper = genshin_helper

    @staticmethod
    async def _execute_queue(
        redeem_task: Coroutine[Any, Any, RedeemResult],
        callback_task: "(result: RedeemResult) -> Coroutine[Any, Any, None]",
    ) -> None:
        data = await redeem_task
        await callback_task(data)

    async def run(
        self,
        data: RedeemResult,
        callback_task: "(result: RedeemResult) -> Coroutine[Any, Any, None]",
        priority: int = 2,
        only_region: bool = False,
    ) -> None:
        redeem_task = self.redeem_code(data, only_region)
        queue_task = RedeemRunnerTask(self._execute_queue(redeem_task, callback_task))
        if priority == 2 and self.queue.qsize() >= (self.queue_size - 1):
            raise RedeemQueueFull()
        if self.queue.full():
            raise RedeemQueueFull()
        self.queue.put([priority, queue_task])
        async with self.sema:
            if not self.queue.empty():
                _, task = self.queue.get()
                await task.run()
                await asyncio.sleep(5)

    async def redeem_code(self, result: RedeemResult, only_region: bool) -> RedeemResult:
        error = None
        try:
            async with self.genshin_helper.genshin(
                result.user_id,
                region=RegionEnum.HOYOLAB if only_region else None,
                player_id=result.uid,
            ) as client:
                client: "GenshinClient"
                result.uid = client.player_id
                await client.redeem_code_by_hoyolab(result.code)
        except RegionNotSupported:
            error = "此服务器暂不支持进行兑换哦~"
        except RedemptionInvalid:
            error = "兑换码格式不正确，请确认。"
        except RedemptionClaimed:
            error = "此兑换码已经兑换过了。"
        except RedemptionCooldown as e:
            error = e.message
        except Exception as e:
            error = str(e)[:500]
        result.error = error
        return result
