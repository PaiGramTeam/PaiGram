from app.wiki.cache import WikiCache
from app.wiki.service import WikiService
from utils.app.manager import listener_service
from utils.redisdb import RedisDB


@listener_service()
def create_wiki_service(redis: RedisDB):
    _cache = WikiCache(redis)
    _service = WikiService(_cache)
    return _service
