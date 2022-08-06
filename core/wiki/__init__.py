from utils.redisdb import RedisDB
from utils.service.manager import listener_service
from .cache import WikiCache
from .services import WikiService


@listener_service()
def create_wiki_service(redis: RedisDB):
    _cache = WikiCache(redis)
    _service = WikiService(_cache)
    return _service
