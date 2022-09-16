import asyncio
import re
from abc import abstractmethod
from asyncio import Queue
from multiprocessing import Value
from ssl import SSLZeroReturnError
from typing import AsyncIterator, ClassVar, List, Optional, Tuple, Union

import anyio
import ujson as json
from bs4 import BeautifulSoup
from httpx import AsyncClient, HTTPError, Response, URL
from pydantic import (
    BaseConfig as PydanticBaseConfig,
    BaseModel as PydanticBaseModel,
)
from typing_extensions import Self

__all__ = ['Model', 'WikiModel', 'SCRAPE_HOST']

SCRAPE_HOST = URL("https://genshin.honeyhunterworld.com/")


class Model(PydanticBaseModel):
    """基类"""

    def __new__(cls, *args, **kwargs):
        # 让每次new的时候都解析
        cls.update_forward_refs()
        return super(Model, cls).__new__(cls)

    class Config(PydanticBaseConfig):
        # 使用 ujson 作为解析库
        json_dumps = json.dumps
        json_loads = json.loads


class WikiModel(Model):
    # noinspection PyUnresolvedReferences
    """wiki所用到的基类

        Attributes:
            id (:obj:`int`): ID
            name (:obj:`str`): 名称
            rarity (:obj:`int`): 星级

            _client (:class:`httpx.AsyncClient`): 发起 http 请求的 client
        """
    _client: ClassVar[AsyncClient] = AsyncClient()

    id: str
    name: str
    rarity: int

    @staticmethod
    @abstractmethod
    def scrape_urls() -> List[URL]:
        """爬取的目标网页集合

        例如有关武器的页面有:
        [单手剑](https://genshin.honeyhunterworld.com/fam_sword/?lang=CHS)
        [双手剑](https://genshin.honeyhunterworld.com/fam_claymore/?lang=CHS)
        [长柄武器](https://genshin.honeyhunterworld.com/fam_polearm/?lang=CHS)
        。。。
        这个函数就是返回这些页面的网址所组成的 List

        """

    @classmethod
    async def _client_get(cls, url: Union[URL, str], retry_times: int = 5, sleep: float = 1) -> Response:
        """用自己的 client 发起 get 请求的快捷函数

        Args:
            url: 发起请求的 url
            retry_times: 发生错误时的重复次数。不能小于 0 .
            sleep: 发生错误后等待重试的时间，单位为秒。
        Returns:
            返回对应的请求
        Raises:
            请求所需要的异常
        """
        for _ in range(retry_times):
            try:
                return await cls._client.get(url, follow_redirects=True)
            except (HTTPError, SSLZeroReturnError):
                await anyio.sleep(sleep)
        return await cls._client.get(url, follow_redirects=True)  # 防止 retry_times 等于 0 的时候无法发生请求

    @classmethod
    @abstractmethod
    async def _parse_soup(cls, soup: BeautifulSoup) -> Self:
        """解析 soup 生成对应 WikiModel

        Args:
            soup: 需要解析的 soup
        Returns:
            返回对应的 WikiModel
        """

    @classmethod
    async def _scrape(cls, url: Union[URL, str]) -> Self:
        """从 url 中爬取数据，并返回对应的 Model

        Args:
            url: 目标 url. 可以为字符串 str , 也可以为 httpx.URL
        Returns:
            返回对应的 WikiModel
        """
        response = await cls._client_get(url)
        return await cls._parse_soup(BeautifulSoup(response.text, 'lxml'))

    @classmethod
    async def get_by_id(cls, id_: str) -> Self:
        """通过ID获取Model

        Args:
            id_: 目标 ID
        Returns:
            返回对应的 WikiModel
        """
        return await cls._scrape(await cls.get_url_by_id(id_))

    @classmethod
    async def get_by_name(cls, name: str) -> Optional[Self]:
        """通过名称获取Model

        Args:
            name: 目标名
        Returns:
            返回对应的 WikiModel
        """
        url = await cls.get_url_by_name(name)
        if url is None:
            return None
        else:
            return await cls._scrape(url)

    @classmethod
    async def get_full_data(cls) -> List[Self]:
        """获取全部数据的 Model

        Returns:
            返回能爬到的所有的 Model 所组成的 List
        """
        return [i async for i in cls.full_data_generator()]

    @classmethod
    async def full_data_generator(cls) -> AsyncIterator[Self]:
        """Model 生成器

        这是一个异步生成器，该函数在使用时会爬取所有数据，并将其转为对应的 Model，然后存至一个队列中
        当有需要时，再一个一个地迭代取出

        Returns:
            返回能爬到的所有的 WikiModel 所组成的 List
        """
        queue: Queue[Self] = Queue()  # 存放 Model 的队列
        signal = Value('i', 0)  # 一个用于异步任务同步的信号

        async def task(u):
            # 包装的爬虫任务
            await queue.put(await cls._scrape(u))  # 爬取一条数据，并将其放入队列中
            signal.value -= 1  # 信号量减少 1 ，说明该爬虫任务已经完成

        for _, url in await cls.get_name_list(with_url=True):  # 遍历爬取所有需要爬取的页面
            signal.value += 1  # 信号量增加 1 ，说明有一个爬虫任务被添加
            asyncio.create_task(task(url))  # 创建一个爬虫任务

        while signal.value > 0 or not queue.empty():  # 当还有未完成的爬虫任务或存放数据的队列不为空时
            yield await queue.get()  # 取出并返回一个存放的 Model

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {super(WikiModel, self).__str__()}>"

    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    async def get_url_by_id(id_: str) -> URL:
        """根据 id 获取对应的 url

        例如神里绫华的ID为 ayaka_002，对应的数据页url为 https://genshin.honeyhunterworld.com/ayaka_002/?lang=CHS

        Args:
            id_ : 实列ID
        Returns:
            返回对应的 url
        """
        return SCRAPE_HOST.join(f"{id_}/?lang=CHS")

    @classmethod
    async def _name_list_generator(cls, *, with_url: bool = False) -> AsyncIterator[Union[str, Tuple[str, URL]]]:
        """一个 Model 的名称 和 其对应 url 的异步生成器

        Args:
            with_url: 是否返回相应的 url
        Returns:
            返回对应的名称列表 或者 名称与url 的列表
        """
        urls = cls.scrape_urls()
        queue: Queue[Union[str, Tuple[str, URL]]] = Queue()  # 存放 Model 的队列
        signal = Value('i', len(urls))  # 一个用于异步任务同步的信号，初始值为存放所需要爬取的页面数

        async def task(page: URL):
            """包装的爬虫任务"""
            response = await cls._client_get(page)
            # 从页面中获取对应的 chaos data (未处理的json格式字符串)
            chaos_data = re.findall(r'sortable_data\.push\((.*)\);\s*sortable_cur_page', response.text)[0]
            json_data = json.loads(chaos_data)  # 转为 json
            for data in json_data:  # 遍历 json
                data_name = re.findall(r'>(.*)<', data[1])[0]  # 获取 Model 的名称
                if with_url:  # 如果需要返回对应的 url
                    data_url = SCRAPE_HOST.join(re.findall(r'\"(.*?)\"', data[0])[0])
                    await queue.put((data_name, data_url))
                else:
                    await queue.put(data_name)
            signal.value = signal.value - 1  # 信号量减少 1 ，说明该爬虫任务已经完成

        for url in urls:  # 遍历需要爬出的页面
            asyncio.create_task(task(url))  # 添加爬虫任务
        while signal.value > 0 or not queue.empty():  # 当还有未完成的爬虫任务或存放数据的队列不为空时
            yield await queue.get()  # 取出并返回一个存放的 Model

    @classmethod
    async def get_name_list(cls, *, with_url: bool = False) -> List[Union[str, Tuple[str, URL]]]:
        """获取全部 Model 的 名称

        Returns:
            返回能爬到的所有的 Model 的名称所组成的 List
        """
        return [i async for i in cls._name_list_generator(with_url=with_url)]

    @classmethod
    async def get_url_by_name(cls, name: str) -> Optional[URL]:
        """通过 Model 的名称获取对应的 url

        Args:
            name: 实列名
        Returns:
            若有对应的实列，则返回对应的 url; 若没有, 则返回 None
        """
        async for n, url in cls._name_list_generator(with_url=True):
            if name == n:
                return url

    @property
    @abstractmethod
    def icon(self):
        """返回此 Model 的图标链接"""
