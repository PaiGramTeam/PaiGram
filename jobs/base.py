import datetime
from typing import Union, Tuple

from telegram.ext import CallbackContext

from model.types import JSONDict, Func


class BaseJobHandler:
    pass


class RunDailyHandler:
    def __init__(self, callback: Func, time: datetime.time, days: Tuple[int, ...] = tuple(range(7)),
                 data: object = None, name: str = None, chat_id: int = None, user_id: int = None,
                 job_kwargs: JSONDict = None, ):
        """Creates a new :class:`Job` that runs on a daily basis and adds it to the queue.

        Note:
            For a note about DST, please see the documentation of `APScheduler`_.

        .. _`APScheduler`: https://apscheduler.readthedocs.io/en/stable/modules/triggers/cron.html
                           #daylight-saving-time-behavior

        Args:
            callback (:term:`coroutine function`): The callback function that should be executed by
                the new job. Callback signature::

                    async def callback(context: CallbackContext)

            time (:obj:`datetime.time`): Time of day at which the job should run. If the timezone
                (:obj:`datetime.time.tzinfo`) is :obj:`None`, the default timezone of the bot will
                be used, which is UTC unless :attr:`telegram.ext.Defaults.tzinfo` is used.
            days (Tuple[:obj:`int`], optional): Defines on which days of the week the job should
                run (where ``0-6`` correspond to sunday - saturday). By default, the job will run
                every day.

                .. versionchanged:: 20.0
                    Changed day of the week mapping of 0-6 from monday-sunday to sunday-saturday.
            data (:obj:`object`, optional): Additional data needed for the callback function.
                Can be accessed through :attr:`Job.data` in the callback. Defaults to
                :obj:`None`.

                .. versionchanged:: 20.0
                    Renamed the parameter ``context`` to :paramref:`data`.
            name (:obj:`str`, optional): The name of the new job. Defaults to
                :external:attr:`callback.__name__ <definition.__name__>`.
            chat_id (:obj:`int`, optional): Chat id of the chat associated with this job. If
                passed, the corresponding :attr:`~telegram.ext.CallbackContext.chat_data` will
                be available in the callback.

                .. versionadded:: 20.0

            user_id (:obj:`int`, optional): User id of the user associated with this job. If
                passed, the corresponding :attr:`~telegram.ext.CallbackContext.user_data` will
                be available in the callback.

                .. versionadded:: 20.0
            job_kwargs (:obj:`dict`, optional): Arbitrary keyword arguments to pass to the
                :meth:`apscheduler.schedulers.base.BaseScheduler.add_job()`.

        """
        # 复制文档
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

    def __init__(self, callback: Func, interval: Union[float, datetime.timedelta],
                 first: Union[float, datetime.timedelta, datetime.datetime, datetime.time] = None,
                 last: Union[float, datetime.timedelta, datetime.datetime, datetime.time] = None,
                 context: object = None, name: str = None, chat_id: int = None, user_id: int = None,
                 job_kwargs: JSONDict = None):
        """Creates a new :class:`Job` instance that runs at specified intervals and adds it to the
        queue.

        Note:
            For a note about DST, please see the documentation of `APScheduler`_.

        .. _`APScheduler`: https://apscheduler.readthedocs.io/en/stable/modules/triggers/cron.html
                           #daylight-saving-time-behavior

        Args:
            callback (:term:`coroutine function`): The callback function that should be executed by
                the new job. Callback signature::

                    async def callback(context: CallbackContext)

            interval (:obj:`int` | :obj:`float` | :obj:`datetime.timedelta`): The interval in which
                the job will run. If it is an :obj:`int` or a :obj:`float`, it will be interpreted
                as seconds.
            first (:obj:`int` | :obj:`float` | :obj:`datetime.timedelta` |                        \
                   :obj:`datetime.datetime` | :obj:`datetime.time`, optional):
                Time in or at which the job should run. This parameter will be interpreted
                depending on its type.

                * :obj:`int` or :obj:`float` will be interpreted as "seconds from now" in which the
                  job should run.
                * :obj:`datetime.timedelta` will be interpreted as "time from now" in which the
                  job should run.
                * :obj:`datetime.datetime` will be interpreted as a specific date and time at
                  which the job should run. If the timezone (:attr:`datetime.datetime.tzinfo`) is
                  :obj:`None`, the default timezone of the bot will be used.
                * :obj:`datetime.time` will be interpreted as a specific time of day at which the
                  job should run. This could be either today or, if the time has already passed,
                  tomorrow. If the timezone (:attr:`datetime.time.tzinfo`) is :obj:`None`, the
                  default timezone of the bot will be used, which is UTC unless
                  :attr:`telegram.ext.Defaults.tzinfo` is used.

                Defaults to :paramref:`interval`
            last (:obj:`int` | :obj:`float` | :obj:`datetime.timedelta` |                        \
                   :obj:`datetime.datetime` | :obj:`datetime.time`, optional):
                Latest possible time for the job to run. This parameter will be interpreted
                depending on its type. See :paramref:`first` for details.

                If :paramref:`last` is :obj:`datetime.datetime` or :obj:`datetime.time` type
                and ``last.tzinfo`` is :obj:`None`, the default timezone of the bot will be
                assumed, which is UTC unless :attr:`telegram.ext.Defaults.tzinfo` is used.

                Defaults to :obj:`None`.
            data (:obj:`object`, optional): Additional data needed for the callback function.
                Can be accessed through :attr:`Job.data` in the callback. Defaults to
                :obj:`None`.

                .. versionchanged:: 20.0
                    Renamed the parameter ``context`` to :paramref:`data`.
            name (:obj:`str`, optional): The name of the new job. Defaults to
                :external:attr:`callback.__name__ <definition.__name__>`.
            chat_id (:obj:`int`, optional): Chat id of the chat associated with this job. If
                passed, the corresponding :attr:`~telegram.ext.CallbackContext.chat_data` will
                be available in the callback.

                .. versionadded:: 20.0

            user_id (:obj:`int`, optional): User id of the user associated with this job. If
                passed, the corresponding :attr:`~telegram.ext.CallbackContext.user_data` will
                be available in the callback.

                .. versionadded:: 20.0
            job_kwargs (:obj:`dict`, optional): Arbitrary keyword arguments to pass to the
                :meth:`apscheduler.schedulers.base.BaseScheduler.add_job()`.

        """
        # 复制文档
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
