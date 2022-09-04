from core.base.mysql import MySQL
from core.service import init_service
from .repositories import UserRepository
from .services import UserService


@init_service
def create_user_service(mysql: MySQL):
    _repository = UserRepository(mysql)
    _service = UserService(_repository)
    return _service
