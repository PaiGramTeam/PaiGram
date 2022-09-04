import random
import re
from typing import List, Optional

from redis import DataError, ResponseError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Poll, \
    ReplyKeyboardRemove, Message
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, MessageHandler, filters
from telegram.helpers import escape_markdown

from core.admin import BotAdminService
from core.quiz import QuizService
from core.quiz.models import Answer, Question
from utils.log import logger
from plugins.base import BasePlugins
from utils.decorators.restricts import restricts
from utils.plugins.manager import listener_plugins_class
from utils.random import MT19937_Random
from utils.service.inject import inject


class QuizCommandData:
    question_id: int = -1
    new_question: str = ""
    new_correct_answer: str = ""
    new_wrong_answer: List[str] = []
    status: int = 0


@listener_plugins_class()
class QuizPlugin(BasePlugins):
    """派蒙的十万个为什么
    合并了问题修改/添加/删除
    """

    CHECK_COMMAND, VIEW_COMMAND, CHECK_QUESTION, \
    GET_NEW_QUESTION, GET_NEW_CORRECT_ANSWER, GET_NEW_WRONG_ANSWER, \
    QUESTION_EDIT, SAVE_QUESTION = range(10300, 10308)

    @inject
    def __init__(self, quiz_service: QuizService = None, bot_admin_service: BotAdminService = None):
        self.bot_admin_service = bot_admin_service
        self.user_time = {}
        self.quiz_service = quiz_service
        self.time_out = 120
        self.random = MT19937_Random()

    @classmethod
    def create_handlers(cls):
        quiz = cls()
        quiz_handler = ConversationHandler(
            entry_points=[CommandHandler('quiz', quiz.command_start, block=True)],
            states={
                quiz.CHECK_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                    quiz.check_command, block=True)],
                quiz.CHECK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                     quiz.check_question, block=True)],
                quiz.GET_NEW_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                       quiz.get_new_question, block=True)],
                quiz.GET_NEW_CORRECT_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                             quiz.get_new_correct_answer, block=True)],
                quiz.GET_NEW_WRONG_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                           quiz.get_new_wrong_answer, block=True),
                                            CommandHandler("finish", quiz.finish_edit)],
                quiz.SAVE_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                    quiz.save_question, block=True)],
            },
            fallbacks=[CommandHandler('cancel', quiz.cancel, block=True)]
        )
        return [quiz_handler]

    async def send_poll(self, update: Update) -> Optional[Message]:
        chat = update.message.chat
        user = update.effective_user
        question_id_list = await self.quiz_service.get_question_id_list()
        if filters.ChatType.GROUPS.filter(update.message):
            logger.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 发送挑战问题命令请求")
            if len(question_id_list) == 0:
                return None
        if len(question_id_list) == 0:
            return None
        index = self.random.random(0, len(question_id_list))
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
        return await update.effective_message.reply_poll(question.text, _options,
                                                         correct_option_id=index, is_anonymous=False,
                                                         open_period=self.time_out, type=Poll.QUIZ)

    @restricts(filters.ChatType.GROUPS, ConversationHandler.END, restricts_time=20, try_delete_message=True)
    @restricts(filters.ChatType.PRIVATE, ConversationHandler.END)
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.message
        if filters.ChatType.PRIVATE.filter(message):
            logger.info(f"用户 {user.full_name}[{user.id}] quiz命令请求")
            admin_list = await self.bot_admin_service.get_admin_list()
            if user.id in admin_list:
                quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
                if quiz_command_data is None:
                    quiz_command_data = QuizCommandData()
                    context.chat_data["quiz_command_data"] = quiz_command_data
                text = f'你好 {user.mention_markdown_v2()} {escape_markdown("！请选择你的操作！")}'
                reply_keyboard = [
                    ["查看问题", "添加问题"],
                    ["重载问题"],
                    ["退出"]
                ]
                await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                                                       one_time_keyboard=True))
                return self.CHECK_COMMAND
            else:
                await self.send_poll(update)
        elif filters.ChatType.GROUPS.filter(update.message):
            await update.message.reply_chat_action(ChatAction.TYPING)
            poll_message = await self.send_poll(update)
            if poll_message is None:
                return ConversationHandler.END
            self._add_delete_message_job(context, update.message.chat_id, update.message.message_id, 300)
            self._add_delete_message_job(context, poll_message.chat_id, poll_message.message_id, 300)
        return ConversationHandler.END

    async def view_command(self, update: Update, _: CallbackContext) -> int:
        keyboard = [
            [
                InlineKeyboardButton(text="选择问题", switch_inline_query_current_chat="查看问题 ")
            ]
        ]
        await update.message.reply_text("请回复你要查看的问题",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return self.CHECK_COMMAND

    async def check_question(self, update: Update, _: CallbackContext) -> int:
        reply_keyboard = [
            ["删除问题"],
            ["退出"]
        ]
        await update.message.reply_text("请选择你的操作", reply_markup=ReplyKeyboardMarkup(reply_keyboard))
        return self.CHECK_COMMAND

    async def check_command(self, update: Update, context: CallbackContext) -> int:
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        if update.message.text == "退出":
            await update.message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif update.message.text == "查看问题":
            return await self.view_command(update, context)
        elif update.message.text == "添加问题":
            return await self.add_question(update, context)
        elif update.message.text == "删除问题":
            return await self.delete_question(update, context)
        # elif update.message.text == "修改问题":
        #    return await self.edit_question(update, context)
        elif update.message.text == "重载问题":
            return await self.refresh_question(update, context)
        else:
            result = re.findall(r"问题ID (\d+)", update.message.text)
            if len(result) == 1:
                try:
                    question_id = int(result[0])
                except ValueError:
                    await update.message.reply_text("获取问题ID失败")
                    return ConversationHandler.END
                quiz_command_data.question_id = question_id
                await update.message.reply_text("获取问题ID成功")
                return await self.check_question(update, context)
            await update.message.reply_text("命令错误", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

    async def refresh_question(self, update: Update, _: CallbackContext) -> int:
        try:
            await self.quiz_service.refresh_quiz()
        except DataError:
            await update.message.reply_text("Redis数据错误，重载失败", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except ResponseError as error:
            logger.error("重载问题失败", error)
            await update.message.reply_text("重载问题失败，异常抛出Redis请求错误异常，详情错误请看日记",
                                            reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await update.message.reply_text("重载成功", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    async def add_question(self, update: Update, context: CallbackContext) -> int:
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        quiz_command_data.new_wrong_answer = []
        quiz_command_data.new_question = ""
        quiz_command_data.new_correct_answer = ""
        quiz_command_data.status = 1
        await update.message.reply_text("请回复你要添加的问题，或发送 /cancel 取消操作", reply_markup=ReplyKeyboardRemove())
        return self.GET_NEW_QUESTION

    async def get_new_question(self, update: Update, context: CallbackContext) -> int:
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        reply_text = f"问题：`{escape_markdown(update.message.text, version=2)}`\n" \
                     f"请填写正确答案："
        quiz_command_data.new_question = update.message.text
        await update.message.reply_markdown_v2(reply_text)
        return self.GET_NEW_CORRECT_ANSWER

    async def get_new_correct_answer(self, update: Update, context: CallbackContext) -> int:
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        reply_text = f"正确答案：`{escape_markdown(update.message.text, version=2)}`\n" \
                     f"请填写错误答案："
        await update.message.reply_markdown_v2(reply_text)
        quiz_command_data.new_correct_answer = update.message.text
        return self.GET_NEW_WRONG_ANSWER

    async def get_new_wrong_answer(self, update: Update, context: CallbackContext) -> int:
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        reply_text = f"错误答案：`{escape_markdown(update.message.text, version=2)}`\n" \
                     f"可继续填写，并使用 {escape_markdown('/finish', version=2)} 结束。"
        await update.message.reply_markdown_v2(reply_text)
        quiz_command_data.new_wrong_answer.append(update.message.text)
        return self.GET_NEW_WRONG_ANSWER

    async def finish_edit(self, update: Update, context: CallbackContext):
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        reply_text = f"问题：`{escape_markdown(quiz_command_data.new_question, version=2)}`\n" \
                     f"正确答案：`{escape_markdown(quiz_command_data.new_correct_answer, version=2)}`\n" \
                     f"错误答案：`{escape_markdown(' '.join(quiz_command_data.new_wrong_answer), version=2)}`"
        await update.message.reply_markdown_v2(reply_text)
        reply_keyboard = [["保存并重载配置", "抛弃修改并退出"]]
        await update.message.reply_text("请核对问题，并选择下一步操作。", reply_markup=ReplyKeyboardMarkup(reply_keyboard))
        return self.SAVE_QUESTION

    async def save_question(self, update: Update, context: CallbackContext):
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        if update.message.text == "抛弃修改并退出":
            await update.message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif update.message.text == "保存并重载配置":
            if quiz_command_data.status == 1:
                answer = [
                    Answer(text=wrong_answer, is_correct=False) for wrong_answer in
                    quiz_command_data.new_wrong_answer
                ]
                answer.append(Answer(text=quiz_command_data.new_correct_answer, is_correct=True))
                await self.quiz_service.save_quiz(
                    Question(text=quiz_command_data.new_question))
                await update.message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
                try:
                    await self.quiz_service.refresh_quiz()
                except ResponseError as error:
                    logger.error("重载问题失败", error)
                    await update.message.reply_text("重载问题失败，异常抛出Redis请求错误异常，详情错误请看日记",
                                                    reply_markup=ReplyKeyboardRemove())
                    return ConversationHandler.END
                await update.message.reply_text("重载配置成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await update.message.reply_text("回复错误，请重新选择")
            return self.SAVE_QUESTION

    async def edit_question(self, update: Update, context: CallbackContext) -> int:
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        quiz_command_data.new_wrong_answer = []
        quiz_command_data.new_question = ""
        quiz_command_data.new_correct_answer = ""
        quiz_command_data.status = 2
        await update.message.reply_text("请回复你要修改的问题", reply_markup=ReplyKeyboardRemove())
        return self.GET_NEW_QUESTION

    async def delete_question(self, update: Update, context: CallbackContext) -> int:
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        # 再问题重载Redis 以免redis数据为空时出现奔溃
        try:
            await self.quiz_service.refresh_quiz()
            question = await self.quiz_service.get_question(quiz_command_data.question_id)
            # 因为外键的存在，先删除答案
            for answer in question.answers:
                await self.quiz_service.delete_question_by_id(answer.answer_id)
            await self.quiz_service.delete_question_by_id(question.question_id)
            await update.message.reply_text("删除问题成功", reply_markup=ReplyKeyboardRemove())
            await self.quiz_service.refresh_quiz()
        except ResponseError as error:
            logger.error("重载问题失败", error)
            await update.message.reply_text("重载问题失败，异常抛出Redis请求错误异常，详情错误请看日记",
                                            reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await update.message.reply_text("重载配置成功", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
