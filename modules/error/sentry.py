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
    def report_error(update: Update, exc_info):
        if not config.error_sentry_dsn:
            return
        try:
            sender_id = update.effective_user.id if update.effective_user else update.effective_chat.id
        except AttributeError:
            sender_id = 0
        sentry_sdk.set_context(
            "Target", {"ChatID": str(update.message.chat_id), "UserID": sender_id, "Msg": update.message.text or ""}
        )
        sentry_sdk.capture_exception(exc_info)
