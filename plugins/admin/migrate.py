from telegram import Update
from telegram.ext import CallbackContext

from core.plugin import Plugin, handler


class MigrateTest(Plugin):
    @handler.command(command="migrate", block=False, admin=True)
    async def get_chat_command(self, update: Update, context: CallbackContext):
        message = update.effective_message
        args = self.get_args(context)
        if (not args) or len(args) < 2:
            await message.reply_text("参数错误，请指定新旧用户 id ！")
            return
        try:
            old_user_id, new_user_id = int(args[0]), int(args[1])
        except ValueError:
            await message.reply_text("参数错误，请指定新旧用户 id ！")
            return
        data = []
        for k, instance in self.application.managers.plugins_map.items():
            if _data := await instance.get_migrate_data(old_user_id, new_user_id):
                data.append(_data)
        if not data:
            await message.reply_text("没有需要迁移的数据！")
            return
        text = "确定迁移以下数据？\n\n"
        for d in data:
            text += f"{await d.migrate_data_msg()}\n"
        await message.reply_text(text)
