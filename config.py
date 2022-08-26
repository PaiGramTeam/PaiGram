import os

import ujson
from dotenv import load_dotenv
from distutils.util import strtobool

from utils.storage import Storage

# take environment variables from .env.
load_dotenv()

env = os.getenv

_config = {
    "debug": bool(strtobool(os.getenv('DEBUG', 'True'))),

    "mysql": {
        "host": env("DB_HOST", "127.0.0.1"),
        "port": int(env("DB_PORT", "3306")),
        "user": env("DB_USERNAME"),
        "password": env("DB_PASSWORD"),
        "database": env("DB_DATABASE"),
    },

    "redis": {
        "host": env("REDIS_HOST", "127.0.0.1"),
        "port": int(env("REDIS_PORT", "6369")),
        "database": int(env("REDIS_DB", "0")),
    },

    # 联系 https://t.me/BotFather 使用 /newbot 命令创建机器人并获取 token
    "bot_token": env("BOT_TOKEN"),

    # 记录错误并发送消息通知开发人员
    "error_notification_chat_id": env("ERROR_NOTIFICATION_CHAT_ID"),

    # 文章推送群组
    "channels": [
        # {"name": "", "chat_id": 1},
        # 在环境变量里的格式是 json: [{"name": "", "chat_id": 1}]
        *ujson.loads(env('CHANNELS', '[]'))
    ],

    # bot 管理员
    "admins": [
        # {"username": "", "user_id": 123},
        # 在环境变量里的格式是 json: [{"username": "", "user_id": 1}]
        *ujson.loads(env('ADMINS', '[]'))
    ],
}

config = Storage(_config)
