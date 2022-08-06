from utils.mysql import MySQL
from utils.service.manager import listener_service
from .repositories import SignRepository
from .services import SignServices


@listener_service()
def create_game_strategy_service(mysql: MySQL):
    _repository = SignRepository(mysql)
    _service = SignServices(_repository)
    return _service
