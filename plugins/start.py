from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext
from telegram.helpers import escape_markdown


async def start(update: Update, _: CallbackContext) -> None:
    user = update.effective_user
    await update.message.reply_markdown_v2(f'你好 {user.mention_markdown_v2()} {escape_markdown("！我是派蒙 ！")}')


async def help_command(update: Update, _: CallbackContext) -> None:
    await update.message.reply_text('前面的区域，以后再来探索吧！')


async def new_chat_members(update: Update, context: CallbackContext) -> None:
    for new_chat_members_data in update.message.new_chat_members:
        if new_chat_members_data.id == context.bot.id:  # 判断是否是机器人第一次入群
            await update.message.reply_text('感谢邀请小派蒙到本群！'
                                            '请使用 /help 查看咱已经学会的功能。')


async def unknown_command(update: Update, _: CallbackContext) -> None:
    await update.message.reply_text('前面的区域，以后再来探索吧！')


async def emergency_food(update: Update, _: CallbackContext) -> None:
    await update.message.reply_text('派蒙才不是应急食品！')


async def ping(update: Update, _: CallbackContext) -> None:
    await update.message.reply_text("online! ヾ(✿ﾟ▽ﾟ)ノ")


async def reply_keyboard_remove(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("移除远程键盘成功", reply_markup=ReplyKeyboardRemove())
    # await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
