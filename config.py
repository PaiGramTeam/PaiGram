import ujson
import os


class Config(object):
    def __init__(self):
        project_path = os.path.dirname(__file__)
        config_file = os.path.join(project_path, './config', 'config.json')
        if not os.path.exists(config_file):
            config_file = os.path.join(project_path, './config', 'config.example.json')

        with open(config_file, 'r', encoding='utf-8') as f:
            self._config_json: dict = ujson.load(f)

        self.DEBUG = self.get_config("debug")
        if type(self.DEBUG) != bool:
            self.DEBUG = False
        self.ADMINISTRATORS = self.get_config("administrators")
        self.MYSQL = self.get_config("mysql")
        self.TELEGRAM = self.get_config("telegram")
        self.FUNCTION = self.get_config("function")

    def get_config(self, name: str):
        return self._config_json.get(name, {})


config = Config()
