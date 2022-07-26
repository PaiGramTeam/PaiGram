from app.user.repositories import UserRepository
from app.user.services import UserService
from utils.app.manager import listener_service
from utils.mysql import MySQL


@listener_service()
def create_user_service(mysql: MySQL):
    _repository = UserRepository(mysql)
    _service = UserService(_repository)
    return _service
