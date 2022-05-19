from typing import cast
from urllib.parse import urlparse, urlencode, ParseResult
from uuid import uuid4

import httpx
from telegram import InlineQueryResultArticle, InputTextMessageContent, Update, InlineQuery, InlineQueryResultPhoto
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext
from telegram.helpers import escape_markdown

from logger import Log
from service import BaseService
from service.base import QuestionData
from metadata.metadata import metadat


class Inline:
    def __init__(self, service: BaseService):
        self.service = service

    async def inline_query(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        ilq = cast(InlineQuery, update.inline_query)
        query = ilq.query
        switch_pm_text = "需要帮助嘛？"
        results_list = []
        args = query.split(" ")
        admin_list = await self.service.admin.get_admin_list()
        if args[0] == "":
            pass
        else:
            if "查看问题" == args[0] and user.id in admin_list:
                async def append_quiz(_results_list, _quiz: QuestionData):
                    correct_answer = ""
                    input_message_content = f"问题ID `{_quiz.question_id}`\n" \
                                            f"问题 `{escape_markdown(_quiz.question, version=2)} \n`"
                    wrong_answer = []
                    for _answer in _quiz.answer:
                        if _answer.is_correct:
                            correct_answer = escape_markdown(_answer.answer, version=2)
                        else:
                            wrong_answer.append(f"`{escape_markdown(_answer.answer, version=2)}`")
                    input_message_content += f"正确答案 `{correct_answer}`\n"
                    input_message_content += f"错误答案 {' '.join(wrong_answer)}"
                    _results_list.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=_quiz.question,
                            description=f"正确答案 {correct_answer}",
                            input_message_content=InputTextMessageContent(input_message_content,
                                                                          parse_mode=ParseMode.MARKDOWN_V2)
                        ))

                quiz_info = await self.service.quiz_service.get_quiz_for_db()
                if len(args) >= 2:
                    search = args[1]
                    for quiz in quiz_info:
                        if search in quiz.question:
                            await append_quiz(results_list, quiz)
                        else:
                            for answer in quiz.answer:
                                if search in answer.answer:
                                    await append_quiz(results_list, quiz)
                else:
                    if len(quiz_info) >= 50:
                        results_list.append(
                            InlineQueryResultArticle(
                                id=str(uuid4()),
                                title="警告！问题数量过度可能无法完全展示",
                                description=f"请在命令后添加空格输入要搜索的题目即可指定搜索",
                                input_message_content=InputTextMessageContent("警告！问题数量过度可能无法完全展示\n"
                                                                              "请在命令后添加空格输入要搜索的题目即可指定搜索")
                            ))
                    for quiz in quiz_info:
                        await append_quiz(results_list, quiz)
            for character_name in metadat.characters_name_list:
                if args[0] in character_name:
                    url = await self.service.get_game_info.get_characters_cultivation_atlas(character_name)
                    if url != "":
                        title = f"{character_name}角色攻略"
                        description = f"{character_name}角色攻略"

                        def url_add_params(_url: str, _params: dict):
                            _pr = urlparse(_url)
                            _prlist = list(_pr)
                            _prlist[4] = urlencode(_params)
                            return ParseResult(*_prlist).geturl()

                        caption = "Form [米游社](https://bbs.mihoyo.com/ys/collection/642956) " \
                                  "Via [猫冬](https://bbs.mihoyo.com/ys/accountCenter/postList?id=74019947) " \
                                  f"查看 [原图]({url})"
                        results_list.append(
                            InlineQueryResultPhoto(
                                id=str(uuid4()),
                                photo_url=url + "?x-oss-process=format,jpg",
                                thumb_url=url_add_params(url, self.service.get_game_info.mihoyo.get_images_params(
                                    resize=300)),
                                title=title,
                                caption=caption,
                                parse_mode=ParseMode.MARKDOWN_V2,
                                description=description
                            )
                        )
            if "查看武器列表并查询" == args[0]:
                for weapons_name in metadat.weapons_name_list:
                    results_list.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=weapons_name,
                            description=f"查看武器列表并查询 {weapons_name}",
                            input_message_content=InputTextMessageContent(f"武器查询{weapons_name}",
                                                                          parse_mode=ParseMode.MARKDOWN_V2)
                        ))

        if len(results_list) == 0:
            results_list.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=f"好像找不到问题呢",
                    description=f"这个问题我也不知道，因为我就是个应急食品。",
                    input_message_content=InputTextMessageContent("这个问题我也不知道，因为我就是个应急食品。"),
                ))
        try:
            await ilq.answer(
                results=results_list,
                switch_pm_text=switch_pm_text,
                switch_pm_parameter="inline_message",
                cache_time=0,
                auto_pagination=True,
            )
        except BadRequest as exc:
            if "Query is too old" in exc.message:  # 过时请求全部忽略
                Log.warning(f"用户 {user.full_name}[{user.id}] inline_query请求过时")
                return
            if "can't parse entities" not in exc.message:
                raise exc
            Log.warning("inline_query发生BadRequest错误", exc_info=exc)
            await ilq.answer(
                results=[],
                switch_pm_text="糟糕，发生错误了。",
                switch_pm_parameter="inline_message",
            )
