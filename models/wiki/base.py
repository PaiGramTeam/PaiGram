import asyncio
import re
from abc import abstractmethod
from asyncio import Queue
from multiprocessing import Value
from typing import TYPE_CHECKING, Union, ClassVar, List, Optional, Tuple, AsyncIterator

import anyio
import ujson as json
from bs4 import BeautifulSoup
from httpx import URL, AsyncClient, ReadTimeout, ConnectTimeout, HTTPError, ConnectError
from pydantic import (
    BaseConfig as PydanticBaseConfig,
    BaseModel as PydanticBaseModel,
)
from typing_extensions import Self

if TYPE_CHECKING:
    from asyncio import Task
    from httpx import Response
    # noinspection PyProtectedMember
    from httpx._types import URLTypes

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
    """wiki所用到的基类

    Attributes:
        id (:obj:`int`): ID
        name (:obj:`str`): 名称
        rarity (:obj:`int`): 星级

        _client (:class:`httpx.AsyncClient`): 发起 http 请求的 client
    """
    _client: ClassVar[AsyncClient] = AsyncClient()

    id: int
    name: str
    rarity: int

    @staticmethod
    @abstractmethod
    def scrape_urls() -> List[URL]:
        """爬取的目标网页集合"""

    @classmethod
    async def _client_get(cls, url: 'URLTypes', retry_times: int = 5, sleep: float = 1) -> 'Response':
        for _ in range(retry_times - 1):
            try:
                return await cls._client.get(url, follow_redirects=True)
            except (ReadTimeout, ConnectTimeout, ConnectError):
                await anyio.sleep(sleep)
        raise HTTPError

    @classmethod
    @abstractmethod
    async def _parse_soup(cls, soup: BeautifulSoup) -> Self:
        """解析 soup 生成对应 WikiModel

        Args:
            soup (:class`:bs4.BeautifulSoup`): 目标 soup
        Returns:
            当前业务对应的 WikiModel
        """

    @classmethod
    async def _scrape(cls, url: 'URLTypes') -> Self:
        """从 url 中爬取数据

        Args:
            url (:obj:`httpx.URL` | :obj:`str`): 目标 url. 可以为字符串(str), 也可以为 httpx.URL
        Returns:
            当前业务对应的 WikiModel
        """
        response = await cls._client_get(url)
        return await cls._parse_soup(BeautifulSoup(response.text, 'lxml'))

    @classmethod
    async def get_by_id(cls, id_: Union[int, str]) -> Self:
        return await cls._scrape(await cls.get_url_by_id(id_))

    @classmethod
    async def get_by_name(cls, name: str) -> Optional[Self]:
        url = await cls.get_url_by_name(name)
        if url is None:
            return None
        else:
            return await cls._scrape(url)

    @classmethod
    async def get_full_data(cls) -> List[Self]:
        return [i async for i in cls._full_data_generator()]

    @classmethod
    async def _full_data_generator(cls) -> AsyncIterator[Self]:
        queue: Queue[Self] = Queue()
        signal = Value('i', 0)

        async def task(u):
            await queue.put(await cls._scrape(u))
            signal.value -= 1

        for _, url in await cls.get_name_list(with_url=True):
            signal.value += 1
            asyncio.create_task(task(url))
        while signal.value > 0 or not queue.empty():
            yield await queue.get()

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {super(WikiModel, self).__str__()}>"

    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    @abstractmethod
    async def get_url_by_id(id_: Union[int, str]) -> URL:
        """根据 id 获取对应的 url

        Args:
            id_ (:obj:`str` | :obj:`int`): 实列ID
        Returns:
            回对应的 url(httpx.URL)
        """

    @classmethod
    async def _name_list_generator(cls, *, with_url: bool = False) -> AsyncIterator[Union[str, Tuple[str, URL]]]:
        urls = cls.scrape_urls()
        queue: Queue[Union[str, Tuple[str, URL]]] = Queue()
        signal = Value('i', len(urls))

        async def get_path_url_list(page: URL, s: Value):
            response = await cls._client_get(page)
            chaos_data = re.findall(r'sortable_data\.push\((.*)\);\s*sortable_cur_page', response.text)[0]
            json_data = json.loads(chaos_data)
            for data in json_data:
                data_name = re.findall(r'>(.*)<', data[1])[0]
                if with_url:
                    data_url = SCRAPE_HOST.join(re.findall(r'\"(.*?)\"', data[0])[0])
                    await queue.put((data_name, data_url))
                else:
                    await queue.put(data_name)
            s.value = s.value - 1

        for url in cls.scrape_urls():
            asyncio.create_task(get_path_url_list(url, signal))
        while signal.value > 0 or not queue.empty():
            yield await queue.get()

    @classmethod
    async def get_name_list(cls, *, with_url: bool = False) -> List[Union[str, Tuple[str, URL]]]:
        return [i async for i in cls._name_list_generator(with_url=with_url)]

    @classmethod
    async def get_url_by_name(cls, name: str) -> Optional[URL]:
        """通过实列名获取对应的 url

        Args:
            name (:obj:`str`): 实列名
        Returns:
            若有对应的实列，则返回对应的 url(httpx.URL); 反之, 则返回 None
        """
        async for n, url in cls._name_list_generator(with_url=True):
            if name == n:
                return url
