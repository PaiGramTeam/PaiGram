from app.user.repositories import UserRepository
from app.user.services import UserService
from utils.mysql import MySQL


def create_service(mysql: MySQL):
    repository = UserRepository(mysql)
    service = UserService(repository)
    return service
