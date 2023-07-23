import datetime
from typing import Optional, Dict, Any

from core.base_service import BaseService
from core.services.task.models import Task, TaskTypeEnum
from core.services.task.repositories import TaskRepository

__all__ = [
    "TaskServices",
    "SignServices",
    "TaskCardServices",
    "TaskResinServices",
    "TaskRealmServices",
    "TaskExpeditionServices",
]


class TaskServices(BaseService):
    TASK_TYPE: TaskTypeEnum

    def __init__(self, task_repository: TaskRepository) -> None:
        self._repository: TaskRepository = task_repository

    async def add(self, task: Task):
        return await self._repository.add(task)

    async def remove(self, task: Task):
        return await self._repository.remove(task)

    async def update(self, task: Task):
        task.time_updated = datetime.datetime.now()
        return await self._repository.update(task)

    async def get_by_user_id(self, user_id: int):
        return await self._repository.get_by_user_id(user_id, self.TASK_TYPE)

    async def get_all(self):
        return await self._repository.get_all(self.TASK_TYPE)

    def create(self, user_id: int, chat_id: int, status: int, data: Optional[Dict[str, Any]] = None):
        return Task(
            user_id=user_id,
            chat_id=chat_id,
            time_created=datetime.datetime.now(),
            status=status,
            type=self.TASK_TYPE,
            data=data,
        )


class SignServices(BaseService):
    TASK_TYPE = TaskTypeEnum.SIGN

    def __init__(self, task_repository: TaskRepository) -> None:
        self._repository: TaskRepository = task_repository

    async def add(self, task: Task):
        return await self._repository.add(task)

    async def remove(self, task: Task):
        return await self._repository.remove(task)

    async def update(self, task: Task):
        task.time_updated = datetime.datetime.now()
        return await self._repository.update(task)

    async def get_by_user_id(self, user_id: int):
        return await self._repository.get_by_user_id(user_id, self.TASK_TYPE)

    async def get_all(self):
        return await self._repository.get_all(self.TASK_TYPE)

    def create(self, user_id: int, chat_id: int, status: int, data: Optional[Dict[str, Any]] = None):
        return Task(
            user_id=user_id,
            chat_id=chat_id,
            time_created=datetime.datetime.now(),
            status=status,
            type=self.TASK_TYPE,
            data=data,
        )


class TaskCardServices(BaseService):
    TASK_TYPE = TaskTypeEnum.CARD

    def __init__(self, task_repository: TaskRepository) -> None:
        self._repository: TaskRepository = task_repository

    async def add(self, task: Task):
        return await self._repository.add(task)

    async def remove(self, task: Task):
        return await self._repository.remove(task)

    async def update(self, task: Task):
        task.time_updated = datetime.datetime.now()
        return await self._repository.update(task)

    async def get_by_user_id(self, user_id: int):
        return await self._repository.get_by_user_id(user_id, self.TASK_TYPE)

    async def get_all(self):
        return await self._repository.get_all(self.TASK_TYPE)

    def create(self, user_id: int, chat_id: int, status: int, data: Optional[Dict[str, Any]] = None):
        return Task(
            user_id=user_id,
            chat_id=chat_id,
            time_created=datetime.datetime.now(),
            status=status,
            type=self.TASK_TYPE,
            data=data,
        )


class TaskResinServices(BaseService):
    TASK_TYPE = TaskTypeEnum.RESIN

    def __init__(self, task_repository: TaskRepository) -> None:
        self._repository: TaskRepository = task_repository

    async def add(self, task: Task):
        return await self._repository.add(task)

    async def remove(self, task: Task):
        return await self._repository.remove(task)

    async def update(self, task: Task):
        task.time_updated = datetime.datetime.now()
        return await self._repository.update(task)

    async def get_by_user_id(self, user_id: int):
        return await self._repository.get_by_user_id(user_id, self.TASK_TYPE)

    async def get_all(self):
        return await self._repository.get_all(self.TASK_TYPE)

    def create(self, user_id: int, chat_id: int, status: int, data: Optional[Dict[str, Any]] = None):
        return Task(
            user_id=user_id,
            chat_id=chat_id,
            time_created=datetime.datetime.now(),
            status=status,
            type=self.TASK_TYPE,
            data=data,
        )


class TaskRealmServices(BaseService):
    TASK_TYPE = TaskTypeEnum.REALM

    def __init__(self, task_repository: TaskRepository) -> None:
        self._repository: TaskRepository = task_repository

    async def add(self, task: Task):
        return await self._repository.add(task)

    async def remove(self, task: Task):
        return await self._repository.remove(task)

    async def update(self, task: Task):
        task.time_updated = datetime.datetime.now()
        return await self._repository.update(task)

    async def get_by_user_id(self, user_id: int):
        return await self._repository.get_by_user_id(user_id, self.TASK_TYPE)

    async def get_all(self):
        return await self._repository.get_all(self.TASK_TYPE)

    def create(self, user_id: int, chat_id: int, status: int, data: Optional[Dict[str, Any]] = None):
        return Task(
            user_id=user_id,
            chat_id=chat_id,
            time_created=datetime.datetime.now(),
            status=status,
            type=self.TASK_TYPE,
            data=data,
        )


class TaskExpeditionServices(BaseService):
    TASK_TYPE = TaskTypeEnum.EXPEDITION

    def __init__(self, task_repository: TaskRepository) -> None:
        self._repository: TaskRepository = task_repository

    async def add(self, task: Task):
        return await self._repository.add(task)

    async def remove(self, task: Task):
        return await self._repository.remove(task)

    async def update(self, task: Task):
        task.time_updated = datetime.datetime.now()
        return await self._repository.update(task)

    async def get_by_user_id(self, user_id: int):
        return await self._repository.get_by_user_id(user_id, self.TASK_TYPE)

    async def get_all(self):
        return await self._repository.get_all(self.TASK_TYPE)

    def create(self, user_id: int, chat_id: int, status: int, data: Optional[Dict[str, Any]] = None):
        return Task(
            user_id=user_id,
            chat_id=chat_id,
            time_created=datetime.datetime.now(),
            status=status,
            type=self.TASK_TYPE,
            data=data,
        )
