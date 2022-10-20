import os

import sentry_sdk
from git.repo import Repo
from git.repo.fun import rev_parse
from sentry_sdk.integrations.excepthook import ExcepthookIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from telegram import Update

from core.config import config
from utils.log import logger

repo = Repo(os.getcwd())
sentry_sdk_git_hash = rev_parse(repo, "HEAD").hexsha
sentry_sdk.init(
    config.error_sentry_dsn,
    traces_sample_rate=1.0,
    release=sentry_sdk_git_hash,
    environment="production",
    integrations=[
        HttpxIntegration(),
        ExcepthookIntegration(always_run=False),
        LoggingIntegration(event_level=50),
        SqlalchemyIntegration(),
    ],
)


class Sentry:
    @staticmethod
    def report_error(update: object, exc_info):
        if not config.error_sentry_dsn:
            return
        logger.info("正在上传日记到 sentry")
        message: str = ""
        chat_id: int = 0
        user_id: int = 0
        if isinstance(update, Update):
            if update.effective_user:
                chat_id = update.effective_user.id
            if update.effective_chat:
                user_id = update.effective_chat.id
            if update.effective_message:
                if update.effective_message.text:
                    message = update.effective_message.text
        sentry_sdk.set_context(
            "Target", {"ChatID": str(chat_id), "UserID": str(user_id), "Msg": message}
        )
        sentry_sdk.capture_exception(exc_info)
        logger.success("上传日记到 sentry 成功")
