import random

from telegram import Chat, Message, Poll, User
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import filters

from core.plugin import Plugin, handler
from core.services.quiz import QuizService
from core.services.users import UserService
from utils.decorators.restricts import restricts
from utils.log import logger

__all__ = ("QuizPlugin",)


class QuizPlugin(Plugin):
    """派蒙的十万个为什么"""

    def __init__(self, quiz_service: QuizService = None, user_service: UserService = None):
        self.user_service = user_service
        self.quiz_service = quiz_service
        self.time_out = 120

    @restricts(restricts_time_of_groups=20)
    @handler.message(filters=filters.Regex("来一道题"))
    @handler.command(command="quiz", block=False)
    async def command_start(self, user: User, message: Message, chat: Chat) -> None:
        await message.reply_chat_action(ChatAction.TYPING)
        question_id_list = await self.quiz_service.get_question_id_list()
        if filters.ChatType.GROUPS.filter(message):
            logger.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 发送挑战问题命令请求")
            if len(question_id_list) == 0:
                return None
        if len(question_id_list) == 0:
            return None
        question_id = random.choice(question_id_list)  # nosec
        question = await self.quiz_service.get_question(question_id)
        _options = []
        correct_option = None
        for answer in question.answers:
            _options.append(answer.text)
            if answer.is_correct:
                correct_option = answer.text
        if correct_option is None:
            question_id = question["question_id"]
            logger.warning(f"Quiz模块 correct_option 异常 question_id[%s] " % question_id)
            return None
        random.shuffle(_options)
        index = _options.index(correct_option)
        try:
            poll_message = await message.reply_poll(
                question.text,
                _options,
                correct_option_id=index,
                is_anonymous=False,
                open_period=self.time_out,
                type=Poll.QUIZ,
            )
        except BadRequest as exc:
            if "Not enough rights" in exc.message:
                poll_message = await message.reply_text("出错了呜呜呜 ~ 权限不足，请请检查投票权限是否开启")
            else:
                raise exc
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(message, delay=300)
            self.add_delete_message_job(poll_message, delay=300)
