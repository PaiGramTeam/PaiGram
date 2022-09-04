from core.base.mysql import MySQL
from core.service import init_service
from .repositories import SignRepository
from .services import SignServices


@init_service
def create_game_strategy_service(mysql: MySQL):
    _repository = SignRepository(mysql)
    _service = SignServices(_repository)
    return _service
