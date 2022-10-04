from telegram import Update
from telegram.ext import CallbackContext

from core.plugin import Plugin, handler


class MetadataPlugin(Plugin):
    def __init__(self):
        ...

    @handler.command('refresh_metadata')
    async def refresh(self, update: Update, context: CallbackContext) -> None:
        ...
