from utils.app.manager import listener_service
from utils.mysql import MySQL
from utils.redisdb import RedisDB
from .cache import PublicCookiesCache
from .repositories import CookiesRepository
from .service import CookiesService, PublicCookiesService


@listener_service()
def create_cookie_service(mysql: MySQL):
    _repository = CookiesRepository(mysql)
    _service = CookiesService(_repository)
    return _service


@listener_service()
def create_public_cookie_service(mysql: MySQL, redis: RedisDB):
    _repository = CookiesRepository(mysql)
    _cache = PublicCookiesCache(redis)
    _service = PublicCookiesService(_repository, _cache)
    return _service
