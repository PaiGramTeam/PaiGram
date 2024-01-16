from core.plugin import Plugin
from core.services.groups import GroupService
from gram_core.handler.grouphandler import GroupHandler


class GroupManage(Plugin):
    def __init__(
        self,
        group_service: GroupService,
    ):
        self.type_handler = None
        self.group_service = group_service

    async def initialize(self) -> None:
        self.type_handler = GroupHandler(self.application)
        self.application.telegram.add_handler(self.type_handler, group=-2)

    async def shutdown(self) -> None:
        self.application.telegram.remove_handler(self.type_handler, group=-2)
