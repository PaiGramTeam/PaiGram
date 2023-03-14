import asyncio
from typing import TypeVar, TYPE_CHECKING, Any, Optional

from telegram import Update
from telegram.ext import ApplicationHandlerStop, BaseHandler

from core.error import ServiceNotFoundError
from core.services.users.services import UserAdminService
from utils.log import logger

if TYPE_CHECKING:
    from core.application import Application
    from telegram.ext import Application as TelegramApplication

RT = TypeVar("RT")
UT = TypeVar("UT")

CCT = TypeVar("CCT", bound="CallbackContext[Any, Any, Any, Any]")


class AdminHandler(BaseHandler[Update, CCT]):
    _lock = asyncio.Lock()

    def __init__(self, handler: BaseHandler[Update, CCT], application: "Application") -> None:
        self.handler = handler
        self.application = application
        self.user_service: Optional["UserAdminService"] = None
        super().__init__(self.handler.callback, self.handler.block)

    def check_update(self, update: object) -> bool:
        if not isinstance(update, Update):
            return False
        return self.handler.check_update(update)

    async def _user_service(self) -> "UserAdminService":
        async with self._lock:
            if self.user_service is not None:
                return self.user_service
            user_service: UserAdminService = self.application.managers.services_map.get(UserAdminService, None)
            if user_service is None:
                raise ServiceNotFoundError("UserAdminService")
            self.user_service = user_service
            return self.user_service

    async def handle_update(
        self,
        update: "UT",
        application: "TelegramApplication[Any, CCT, Any, Any, Any, Any]",
        check_result: Any,
        context: "CCT",
    ) -> RT:
        user_service = await self._user_service()
        user = update.effective_user
        if await user_service.is_admin(user.id):
            return await self.handler.handle_update(update, application, check_result, context)
        message = update.effective_message
        logger.warning("用户 %s[%s] 触发尝试调用Admin命令但权限不足", user.full_name, user.id)
        await message.reply_text("权限不足")
        raise ApplicationHandlerStop
