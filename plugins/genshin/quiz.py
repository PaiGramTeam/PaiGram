import random

from telegram import Update, Poll
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, filters

from core.admin import BotAdminService
from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from core.quiz import QuizService
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class QuizPlugin(Plugin, BasePlugin):
    """派蒙的十万个为什么"""

    def __init__(self, quiz_service: QuizService = None, bot_admin_service: BotAdminService = None):
        self.bot_admin_service = bot_admin_service
        self.quiz_service = quiz_service
        self.time_out = 120

    @handler(CommandHandler, command="quiz", block=False)
    @restricts(restricts_time_of_groups=20)
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        chat = message.chat
        await message.reply_chat_action(ChatAction.TYPING)
        question_id_list = await self.quiz_service.get_question_id_list()
        if filters.ChatType.GROUPS.filter(message):
            logger.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 发送挑战问题命令请求")
            if len(question_id_list) == 0:
                return None
        if len(question_id_list) == 0:
            return None
        index = random.choice(question_id_list)  # nosec
        question = await self.quiz_service.get_question(question_id_list[index])
        _options = []
        correct_option = None
        for answer in question.answers:
            _options.append(answer.text)
            if answer.is_correct:
                correct_option = answer.text
        if correct_option is None:
            question_id = question["question_id"]
            logger.warning(f"Quiz模块 correct_option 异常 question_id[{question_id}] ")
            return None
        random.shuffle(_options)
        index = _options.index(correct_option)
        poll_message = await update.effective_message.reply_poll(
            question.text,
            _options,
            correct_option_id=index,
            is_anonymous=False,
            open_period=self.time_out,
            type=Poll.QUIZ,
        )
        if filters.ChatType.GROUPS.filter(message):
            self._add_delete_message_job(context, update.message.chat_id, update.message.message_id, 300)
            self._add_delete_message_job(context, poll_message.chat_id, poll_message.message_id, 300)
