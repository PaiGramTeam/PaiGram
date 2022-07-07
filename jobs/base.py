import datetime
from typing import Union, Tuple

from telegram.ext import CallbackContext
from telegram.ext._utils.types import JobCallback

from model.types import JSONDict


class BaseJobHandler:
    pass


class RunDailyHandler:
    def __init__(self, callback: JobCallback, time: datetime.time, days: Tuple[int, ...] = tuple(range(7)),
                 data: object = None, name: str = None, chat_id: int = None, user_id: int = None,
                 job_kwargs: JSONDict = None,):
        self.job_kwargs = job_kwargs
        self.user_id = user_id
        self.chat_id = chat_id
        self.name = name
        self.data = data
        self.days = days
        self.time = time
        self.callback = callback

    @property
    def get_kwargs(self) -> dict:
        kwargs = {
            "callback": self.callback,
            "time": self.time,
            "days": self.days,
            "data": self.data,
            "name": self.name,
            "chat_id": self.chat_id,
            "user_id": self.callback,
            "job_kwargs": self.job_kwargs,
        }
        return kwargs


class RunRepeatingHandler:

    def __init__(self, callback: JobCallback, interval: Union[float, datetime.timedelta],
                 first: Union[float, datetime.timedelta, datetime.datetime, datetime.time] = None,
                 last: Union[float, datetime.timedelta, datetime.datetime, datetime.time] = None,
                 context: object = None, name: str = None, chat_id: int = None, user_id: int = None,
                 job_kwargs: JSONDict = None):
        self.callback = callback
        self.interval = interval
        self.first = first
        self.last = last
        self.context = context
        self.name = name
        self.chat_id = chat_id
        self.user_id = user_id
        self.job_kwargs = job_kwargs

    @property
    def get_kwargs(self) -> dict:
        kwargs = {
            "callback": self.callback,
            "interval": self.interval,
            "first": self.first,
            "last": self.last,
            "context": self.context,
            "name": self.name,
            "chat_id": self.chat_id,
            "user_id": self.callback,
            "job_kwargs": self.job_kwargs,
        }
        return kwargs


class BaseJob:

    @staticmethod
    def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
        current_jobs = context.job_queue.get_jobs_by_name(name)
        context.job_queue.run_repeating()
        if not current_jobs:
            return False
        for job in current_jobs:
            job.schedule_removal()
        return True
