from utils.apps.manager import listener_service
from utils.mysql import MySQL
from .repositories import SignRepository
from .services import SignServices


@listener_service()
def create_game_strategy_service(mysql: MySQL):
    _repository = SignRepository(mysql)
    _service = SignServices(_repository)
    return _service
