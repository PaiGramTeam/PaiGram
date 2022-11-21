import os

import sentry_sdk
from git.repo import Repo
from git.repo.fun import rev_parse
from sentry_sdk.integrations.excepthook import ExcepthookIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from telegram import Update

__all__ = ["Sentry"]


class Sentry:
    def __init__(self, sentry_dsn: str):
        self.sentry_dsn = sentry_dsn
        repo = Repo(os.getcwd())
        sentry_sdk_git_hash = rev_parse(repo, "HEAD").hexsha
        sentry_sdk.init(
            sentry_dsn,
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

    def report_error(self, update: object, exc_info):
        if not self.sentry_dsn:
            return
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
        sentry_sdk.set_context("Target", {"ChatID": str(chat_id), "UserID": str(user_id), "Msg": message})
        sentry_sdk.capture_exception(exc_info)
