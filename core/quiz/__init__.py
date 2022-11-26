from core.base.mysql import MySQL
from core.base.redisdb import RedisDB
from core.service import init_service

from .cache import QuizCache
from .repositories import QuizRepository
from .services import QuizService


@init_service
def create_quiz_service(mysql: MySQL, redis: RedisDB):
    _repository = QuizRepository(mysql)
    _cache = QuizCache(redis)
    _service = QuizService(_repository, _cache)
    return _service
