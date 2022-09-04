from core.base.redisdb import RedisDB
from core.service import init_service
from .cache import WikiCache
from .services import WikiService


@init_service
def create_wiki_service(redis: RedisDB):
    _cache = WikiCache(redis)
    _service = WikiService(_cache)
    return _service
