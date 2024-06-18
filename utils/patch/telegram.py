import telegram

from utils.patch.methods import patch, patchable

# https://github.com/python-telegram-bot/python-telegram-bot/issues/4295


@patch(telegram.Bot)
class Bot:
    @patchable
    def _effective_inline_results(self, results, next_offset=None, current_offset=None):
        if current_offset == "[]":
            current_offset = 50
        return self.old__effective_inline_results(results, next_offset, current_offset)
