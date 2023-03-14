import asyncio
from typing import TypeVar, Optional

from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop, TypeHandler

from utils.log import logger

UT = TypeVar("UT")
CCT = TypeVar("CCT", bound="CallbackContext[Any, Any, Any, Any]")


class LimiterHandler(TypeHandler[UT, CCT]):
    _lock = asyncio.Lock()

    def __init__(
        self, max_rate: float = 5, time_period: float = 10, amount: float = 1, limit_time: Optional[float] = None
    ):
        """Limiter Handler 通过
        `Leaky bucket algorithm <https://en.wikipedia.org/wiki/Leaky_bucket>`_
        实现对用户的输入的精确控制

        输入超过一定速率后，代码会抛出
        :class:`telegram.ext.ApplicationHandlerStop`
        异常并在一段时间内防止用户执行任何其他操作

        :param max_rate: 在抛出异常之前最多允许 频率/秒 的速度
        :param time_period: 在限制速率的时间段的持续时间
        :param amount: 提供的容量
        :param limit_time: 限制时间 如果不提供限制时间为 max_rate / time_period * amount
        """
        self.max_rate = max_rate
        self.amount = amount
        self._rate_per_sec = max_rate / time_period
        self.limit_time = limit_time
        super().__init__(Update, self.limiter_callback)

    async def limiter_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.inline_query is not None:
            return
        loop = asyncio.get_running_loop()
        async with self._lock:
            time = loop.time()
            user_data = context.user_data
            if user_data is None:
                return
            user_limit_time = user_data.get("limit_time")
            if user_limit_time is not None:
                if time >= user_limit_time:
                    del user_data["limit_time"]
                else:
                    raise ApplicationHandlerStop
            last_task_time = user_data.get("last_task_time", 0)
            if last_task_time:
                task_level = user_data.get("task_level", 0)
                elapsed = time - last_task_time
                decrement = elapsed * self._rate_per_sec
                task_level = max(task_level - decrement, 0)
                user_data["task_level"] = task_level
                if not task_level + self.amount <= self.max_rate:
                    if self.limit_time:
                        limit_time = self.limit_time
                    else:
                        limit_time = 1 / self._rate_per_sec * self.amount
                    user_data["limit_time"] = time + limit_time
                    user = update.effective_user
                    logger.warning("用户 %s[%s] 触发洪水限制 已被限制 %s 秒", user.full_name, user.id, limit_time)
                    raise ApplicationHandlerStop
            user_data["last_task_time"] = time
            task_level = user_data.get("task_level", 0)
            user_data["task_level"] = task_level + self.amount
