from utils.mysql import MySQL
from utils.redisdb import RedisDB
from utils.service.manager import listener_service
from .cache import QuizCache
from .repositories import QuizRepository
from .services import QuizService


@listener_service()
def create_quiz_service(mysql: MySQL, redis: RedisDB):
    _repository = QuizRepository(mysql)
    _cache = QuizCache(redis)
    _service = QuizService(_repository, _cache)
    return _service
