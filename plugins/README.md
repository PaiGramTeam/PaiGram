# plugins 目录

## 说明

该目录仅限处理交互层和业务层数据交换的任务

如有任何新业务接口，请转到 `service` 目录添加

如有任何API请求接口，请转到 `model` 目录添加

## 基础代码

``` python
from telegram.ext import CommandHandler, CallbackContext

from logger import Log
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.plugins.manager import listener_plugins_class

@listener_plugins_class()
class Example:

    @classmethod
    def create_handlers(cls):
        example = cls()
        return [CommandHandler('example', example.command_start)]

    @error_callable
    @restricts()
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        Log.info(f"用户 {user.full_name}[{user.id}] 发出example命令")
        await message.reply_text("Example")

```

### 注意

plugins 模块下的类必须提供 `create_handlers` 类方法作为构建相应处理程序给 `handle.py`

在函数注册为命令处理过程（如 `CommandHandler` ）需要添加 `error_callable` 修饰器作为错误统一处理

如果套引用服务，参数需要声明需要引用服务的类型，并且添加 `inject` 修饰器

必要的函数必须捕获异常后通知用户或者直接抛出异常

入口函数必须使用 `@restricts()` 修饰器 预防洪水攻击

只需在构建的类前加上 `@listener_plugins_class()` 修饰器即可向程序注册插件

**注意：`@restricts()` 修饰器带参，必须带括号，否则会出现调用错误**
