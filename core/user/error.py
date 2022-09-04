class UserNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"user not found, user_id: {user_id}")
