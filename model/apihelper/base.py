import imghdr
from enum import Enum


class ArtworkImage:

    def __init__(self, art_id: int, page: int = 0, is_error: bool = False, data: bytes = b""):
        self.art_id = art_id
        self.data = data
        self.is_error = is_error
        if not is_error:
            self.format: str = imghdr.what(None, self.data)
        self.page = page


class BaseResponseData:
    def __init__(self, response=None, error_message: str = ""):
        if response is None:
            self.error: bool = True
            self.message: str = error_message
            return
        self.response: dict = response
        self.code = response["retcode"]
        if self.code == 0:
            self.error = False
        else:
            self.error = True
        self.message = response["message"]
        self.data = response["data"]


class Stat:
    def __init__(self, view_num: int = 0, reply_num: int = 0, like_num: int = 0, bookmark_num: int = 0,
                 forward_num: int = 0):
        self.forward_num = forward_num  # 关注数
        self.bookmark_num = bookmark_num  # 收藏数
        self.like_num = like_num  # 喜欢数
        self.reply_num = reply_num  # 回复数
        self.view_num = view_num  # 观看数


class ArtworkInfo:
    def __init__(self, post_id: int = 0, subject: str = "", tags=None,
                 image_url_list=None, stat: Stat = None, uid: int = 0, created_at: int = 0):
        if tags is None:
            self.tags = []
        else:
            self.tags = tags
        if image_url_list is None:
            self.image_url_list = []
        else:
            self.image_url_list = image_url_list
        self.Stat = stat
        self.created_at = created_at
        self.uid = uid
        self.subject = subject
        self.post_id = post_id


class HyperionResponse:
    def __init__(self, response=None, error_message: str = ""):
        if response is None:
            self.error: bool = True
            self.message: str = error_message
            return
        self.response: dict = response
        self.code = response["retcode"]
        if self.code == 0:
            self.error = False
        else:
            if self.code == 1102:
                self.message = "作品不存在"
            self.error = True
            return
        if response["data"] is None:
            self.error = True
        self.message: str = response["message"]
        if self.error:
            return
        try:
            self._data_post = response["data"]["post"]
            post = self._data_post["post"]  # 投稿信息
            post_id = post["post_id"]
            subject = post["subject"]  # 介绍，类似title标题
            created_at = post["created_at"]  # 创建时间
            user = self._data_post["user"]  # 用户数据
            uid = user["uid"]  # 用户ID
            topics = self._data_post["topics"]  # 存放 Tag
            image_list = self._data_post["image_list"]  # image_list
        except (AttributeError, TypeError) as err:
            self.error: bool = True
            self.message: str = err
            return
        topics_list = []
        image_url_list = []
        for topic in topics:
            topics_list.append(topic["name"])
        for image in image_list:
            image_url_list.append(image["url"])
        self.post_id = post["post_id"]
        self.user_id = user["uid"]
        self.created_at = post["created_at"]
        stat = Stat(view_num=self._data_post["stat"]["view_num"],
                    reply_num=self._data_post["stat"]["reply_num"],
                    like_num=self._data_post["stat"]["like_num"],
                    bookmark_num=self._data_post["stat"]["bookmark_num"],
                    forward_num=self._data_post["stat"]["forward_num"],
                    )
        self.results = ArtworkInfo(
            subject=subject,
            created_at=created_at,
            uid=uid,
            stat=stat,
            tags=topics_list,
            post_id=post_id,
            image_url_list=image_url_list
        )

    def __bool__(self):
        return self.error

    def __len__(self):
        return len(self.results.image_url_list)


class ServiceEnum(Enum):
    HYPERION = 1
    HOYOLAB = 2
