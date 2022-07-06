# plugins 目录

## 说明

该目录仅限处理交互层和业务层数据交换的任务

如有任何新业务接口，请转到 `service` 目录添加

如有任何API请求接口，请转到 `model` 目录添加

## 基础代码

``` python
from telegram import Update

from manager import listener_plugins_class
from plugins.base import BasePlugins, restricts
from plugins.errorhandler import conversation_error_handler
from utils.base import PaimonContext

@listener_plugins_class()
class Example(BasePlugins):

    @classmethod
    def create_handlers(cls):
        example = cls()
        return [CommandHandler('example', example.command_start)]

    @conversation_error_handler
    @restricts()
    async def command_start(self, update: Update, context: PaimonContext) -> None:
        await message.reply_text("Example")

```

### 注意

plugins 模块下的类需要继承 `BasePlugins`

plugins 模块下的类必须提供 `create_handlers` 静态函数作为构建相应处理程序给 `handle.py`

在函数注册为命令处理过程（如 `CommandHandler` ）需要添加 `conversation_error_handler` 修饰器作为错误统一处理

必要的函数必须捕获异常后通知用户或者直接抛出异常

入口函数必须使用 `@restricts()` 修饰器  防止洪水攻击 

我也不知道从那个版本开始 `plugins` 文件夹下的全部模块无需再次修改 `handler` 文件实现注册处理程序

只需在构建的类前加上 `@listener_plugins_class()` 修饰器即可

**注意：`@restricts()` 修饰器带参，必须带括号，否则会出现调用错误**

如果 `service` 需要全局共用，可以参考 `daily_note.py` 代码

