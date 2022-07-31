from app.cookies.repositories import CookiesRepository
from app.cookies.service import CookiesService
from utils.app.manager import listener_service
from utils.mysql import MySQL


@listener_service()
def create_cookie_service(mysql: MySQL):
    _repository = CookiesRepository(mysql)
    _service = CookiesService(_repository)
    return _service
