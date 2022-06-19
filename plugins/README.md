# plugins 目录

## 说明

该目录仅限处理交互层和业务层数据交换的任务

如有任何新业务接口，请转到 `service` 目录添加

如有任何API请求接口，请转到 `model` 目录添加

## 基础代码

``` python
from telegram import Update
from telegram.ext import CallbackContext

from plugins.base import BasePlugins
from plugins.errorhandler import conversation_error_handler

class Example(BasePlugins):

    @staticmethod
    def create_conversation_handler(service: BaseService):
        example = Example(service)
        return CommandHandler('example', example.command_start)

    @conversation_error_handler
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        await message.reply_text("Example")

```

### 注意

plugins 模块下的类需要继承 `BasePlugins`

plugins 模块下的类必须提供 `create_conversation_handler` 静态函数作为构建相应会话过程给 `handle.py`

在函数注册为命令处理过程（如 `CommandHandler` ）需要添加 `conversation_error_handler` 修饰器作为错误统一处理

必要的函数必须捕获异常后通知用户或者直接抛出异常