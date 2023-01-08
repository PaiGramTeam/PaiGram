class PlayersNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"players not found, user_id: {user_id}")
