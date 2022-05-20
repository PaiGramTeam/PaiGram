import random
import re
import time
from typing import List, Optional

from numpy.random import MT19937, Generator
from redis import DataError, ResponseError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Poll, \
    ReplyKeyboardRemove, Message
from telegram.error import BadRequest
from telegram.ext import CallbackContext, filters, ConversationHandler
from telegram.helpers import escape_markdown

from logger import Log
from plugins.base import BasePlugins
from service import BaseService
from service.base import QuestionData, AnswerData


class QuizCommandData:
    question_id: int = -1
    new_question: str = ""
    new_correct_answer: str = ""
    new_wrong_answer: List[str] = []
    status: int = 0


class Quiz(BasePlugins):
    CHECK_COMMAND, VIEW_COMMAND, CHECK_QUESTION, \
    GET_NEW_QUESTION, GET_NEW_CORRECT_ANSWER, GET_NEW_WRONG_ANSWER, \
    QUESTION_EDIT, SAVE_QUESTION = range(10300, 10308)

    def __init__(self, service: BaseService):
        super().__init__(service)
        self.user_time = {}
        self.send_time = time.time()
        self.generator = Generator(MT19937(int(self.send_time)))
        self.service = service
        self.time_out = 120

    def random(self, low: int, high: int) -> int:
        if self.send_time + 24 * 60 * 60 >= time.time():
            self.send_time = time.time()
            self.generator = Generator(MT19937(int(self.send_time)))
        return int(self.generator.uniform(low, high))

    async def send_poll(self, update: Update) -> Optional[Message]:
        chat = update.message.chat
        user = update.effective_user
        question_id_list = await self.service.quiz_service.get_question_id_list()
        if filters.ChatType.GROUPS.filter(update.message):
            Log.info(f"用户 {user.full_name}[{user.id}] 在群 {chat.title}[{chat.id}] 发送挑战问题命令请求")
            if len(question_id_list) == 0:
                await update.message.reply_text(f"旅行者！！！派蒙的问题清单你还没给我！！快去私聊我给我问题！")
        if len(question_id_list) == 0:
            return None
        index = self.random(0, len(question_id_list))
        question = await self.service.quiz_service.get_question(question_id_list[index])
        options = []
        correct_option = ""
        for answer_id in question["answer_id"]:
            answer = await self.service.quiz_service.get_answer(answer_id)
            options.append(answer["answer"])
            if answer["is_correct"] == 1:
                correct_option = answer["answer"]
        random.shuffle(options)
        index = options.index(correct_option)
        return await update.effective_message.reply_poll(question["question"], options,
                                                         correct_option_id=index, is_anonymous=False,
                                                         open_period=self.time_out, type=Poll.QUIZ)

    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.message
        if filters.ChatType.PRIVATE.filter(message):
            Log.info(f"用户 {user.full_name}[{user.id}] quiz命令请求")
            admin_list = await self.service.admin.get_admin_list()
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
            try:
                command_time = self.user_time.get(f"{user.id}")
                if command_time is None:
                    self.user_time[f"{user.id}"] = time.time()
                else:
                    if time.time() - command_time <= 10:
                        try:
                            await message.delete()
                        except BadRequest as error:
                            Log.warning("删除消息失败", error)
                            pass
                        return ConversationHandler.END
                    else:
                        self.user_time[f"{user.id}"] = time.time()
            except (ValueError, KeyError) as error:
                Log.error("quiz模块 user_time 操作失败", error)
                pass
            poll_message = await self.send_poll(update)
            if poll_message is None:
                return ConversationHandler.END
            self._add_delete_message_job(context, update.message.chat_id, update.message.message_id, 300)
            self._add_delete_message_job(context, poll_message.chat_id, poll_message.message_id, 300)
        return ConversationHandler.END

    async def view_command(self, update: Update, context: CallbackContext) -> int:
        keyboard = [
            [
                InlineKeyboardButton(text="选择问题", switch_inline_query_current_chat="查看问题 ")
            ]
        ]
        await update.message.reply_text("请回复你要查看的问题",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return self.CHECK_COMMAND

    async def check_question(self, update: Update, context: CallbackContext) -> int:
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

    async def refresh_question(self, update: Update, context: CallbackContext) -> int:
        try:
            await self.service.quiz_service.refresh_quiz()
        except DataError:
            await update.message.reply_text("Redis数据错误，重载失败", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        except ResponseError as error:
            Log.error("重载问题失败 /n", error)
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
                    AnswerData(answer=wrong_answer, is_correct=False) for wrong_answer in
                    quiz_command_data.new_wrong_answer
                ]
                answer.append(AnswerData(answer=quiz_command_data.new_correct_answer, is_correct=True))
                await self.service.quiz_service.save_quiz(
                    QuestionData(question=quiz_command_data.new_question, answer=answer))
                await update.message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
                try:
                    await self.service.quiz_service.refresh_quiz()
                except ResponseError as error:
                    Log.error("重载问题失败 /n", error)
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
            await self.service.quiz_service.refresh_quiz()
            question = await self.service.quiz_service.get_question(quiz_command_data.question_id)
            # 因为外键的存在，先删除答案
            for answer_id in question["answer_id"]:
                await self.service.repository.delete_answer(answer_id)
            await self.service.repository.delete_question(question["question_id"])
            await update.message.reply_text("删除问题成功", reply_markup=ReplyKeyboardRemove())
            await self.service.quiz_service.refresh_quiz()
        except ResponseError as error:
            Log.error("重载问题失败 /n", error)
            await update.message.reply_text("重载问题失败，异常抛出Redis请求错误异常，详情错误请看日记",
                                            reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await update.message.reply_text("重载配置成功", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
