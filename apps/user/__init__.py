from utils.mysql import MySQL
from utils.service.manager import listener_service
from .repositories import UserRepository
from .services import UserService


@listener_service()
def create_user_service(mysql: MySQL):
    _repository = UserRepository(mysql)
    _service = UserService(_repository)
    return _service
