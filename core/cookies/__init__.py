from core.base.mysql import MySQL
from core.base.redisdb import RedisDB
from core.cookies.cache import PublicCookiesCache
from core.cookies.repositories import CookiesRepository
from core.cookies.services import CookiesService, PublicCookiesService
from core.service import init_service


@init_service
def create_cookie_service(mysql: MySQL):
    _repository = CookiesRepository(mysql)
    _service = CookiesService(_repository)
    return _service


@init_service
def create_public_cookie_service(mysql: MySQL, redis: RedisDB):
    _repository = CookiesRepository(mysql)
    _cache = PublicCookiesCache(redis)
    _service = PublicCookiesService(_repository, _cache)
    return _service
