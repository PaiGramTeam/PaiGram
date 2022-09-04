import re
from typing import List

from redis import DataError, ResponseError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.baseplugin import BasePlugin
from core.plugin import Plugin, conversation, handler
from core.quiz import QuizService
from core.quiz.models import Answer, Question
from utils.decorators.admins import bot_admins_rights_check
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class QuizCommandData:
    question_id: int = -1
    new_question: str = ""
    new_correct_answer: str = ""
    new_wrong_answer: List[str] = []
    status: int = 0


CHECK_COMMAND, VIEW_COMMAND, CHECK_QUESTION, GET_NEW_QUESTION, GET_NEW_CORRECT_ANSWER, GET_NEW_WRONG_ANSWER, \
QUESTION_EDIT, SAVE_QUESTION = range(10300, 10308)


class SetQuizPlugin(Plugin.Conversation, BasePlugin):
    """派蒙的十万个为什么问题修改/添加/删除"""

    def __init__(self, quiz_service: QuizService = None):
        self.quiz_service = quiz_service
        self.time_out = 120

    @conversation.entry_point
    @handler.command(command='set_quiz', filters=filters.ChatType.PRIVATE, block=True)
    @restricts()
    @bot_admins_rights_check
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.message
        logger.info(f"用户 {user.full_name}[{user.id}] set_quiz命令请求")
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
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return self.CHECK_COMMAND

    async def view_command(self, update: Update, _: CallbackContext) -> int:
        keyboard = [
            [
                InlineKeyboardButton(text="选择问题", switch_inline_query_current_chat="查看问题 ")
            ]
        ]
        await update.message.reply_text("请回复你要查看的问题",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return self.CHECK_COMMAND

    @conversation.state(state=CHECK_QUESTION)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    async def check_question(self, update: Update, _: CallbackContext) -> int:
        reply_keyboard = [
            ["删除问题"],
            ["退出"]
        ]
        await update.message.reply_text("请选择你的操作", reply_markup=ReplyKeyboardMarkup(reply_keyboard))
        return self.CHECK_COMMAND

    @conversation.state(state=CHECK_COMMAND)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
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

    @conversation.state(state=GET_NEW_QUESTION)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    async def get_new_question(self, update: Update, context: CallbackContext) -> int:
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        reply_text = f"问题：`{escape_markdown(update.message.text, version=2)}`\n" \
                     f"请填写正确答案："
        quiz_command_data.new_question = update.message.text
        await update.message.reply_markdown_v2(reply_text)
        return self.GET_NEW_CORRECT_ANSWER

    @conversation.state(state=GET_NEW_CORRECT_ANSWER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    async def get_new_correct_answer(self, update: Update, context: CallbackContext) -> int:
        quiz_command_data: QuizCommandData = context.chat_data.get("quiz_command_data")
        reply_text = f"正确答案：`{escape_markdown(update.message.text, version=2)}`\n" \
                     f"请填写错误答案："
        await update.message.reply_markdown_v2(reply_text)
        quiz_command_data.new_correct_answer = update.message.text
        return self.GET_NEW_WRONG_ANSWER

    @conversation.state(state=GET_NEW_WRONG_ANSWER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @handler.command(command='finish_edit', block=True)
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

    @conversation.state(state=SAVE_QUESTION)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
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
