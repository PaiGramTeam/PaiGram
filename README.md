<h1 align="center">TGPaimonBot v3</h1>

<div align="center">
<img src="https://img.shields.io/badge/python-3.8%2B-blue" alt="python">
<img src="https://img.shields.io/badge/works%20on-my%20machine-brightgreen" alt="">
<img src="https://img.shields.io/badge/status-%E5%92%95%E5%92%95%E5%92%95-blue" alt="">
<a href="https://www.codacy.com/gh/luoshuijs/TGPaimonBot/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=luoshuijs/TGPaimonBot&amp;utm_campaign=Badge_Grade">
    <img src="https://app.codacy.com/project/badge/Grade/810a80be4cbe4b7284ab7634941423c4" alt=""/>
</a>
</div>

---

[v3](https://github.com/luoshuijs/TGPaimonBot/tree/v3) 正在构建中。。。

## 新版插件 Plugin 的写法

### 关于路径

插件应该写在 `plugins` 文件夹下，可以是一个包或者是一个文件，但文件名、文件夹名中不能包含`_`字符

### 关于类

1. 除了要使用`ConversationHandler` 的插件外，都要继承 `core.plugin.Plugin`

   ```python
   from core.plugin import Plugin
   
   
   class TestPlugin(Plugin):
       pass
   ```

2. 针对要用 `ConversationHandler` 的插件，要继承 `core.plugin.Plugin.Conversation`

   ```python
   from core.plugin import Plugin
   
   
   class TestConversationPlugin(Plugin.Conversation):
       pass
   ```

3. 关于初始化方法以及依赖注入

   初始化类, 可写在 `__init__` 和 `__async_init__` 中, 其中 `__async_init__` 应该是异步方法,
   用于执行初始化时需要的异步操作. 这两个方法的执行顺序是 `__init__` 在前, `__async_init__` 在后

   若需要注入依赖, 直接在插件类的`__init__`方法中，提供相应的参数以及标注标注即可, 例如我需要注入一个 `MySQL`

   ```python
   from service.mysql import MySQL
   from core.plugin import Plugin
   
   class TestPlugin(Plugin):
      def __init__(self, mysql: MySQL):
          self.mysql = mysql
   
      async def __async_init__(self):
         """do something"""
   
   ```

## 关于 `handler`

给函数加上 `core.plugin.handler` 这一装饰器即可将这个函数注册为`handler`

### 非 `ConversationHandler` 的 `handler`

1. 直接使用 `core.plugin.handler` 装饰器

   第一个参数是 `handler` 的种类，后续参数为该 `handler` 除 `callback` 参数外的其余参数

   ```python
   from core.plugin import Plugin, handler
   from telegram import Update
   from telegram.ext import CommandHandler, CallbackContext
   
   
   class TestPlugin(Plugin):
       @handler(CommandHandler, command='start', block=False)
       async def start(self, update: Update, context: CallbackContext):
           await update.effective_chat.send_message('hello world!')
   ```

   比如上面代码中的 `command='start', block=False` 就是 `CommandHandler` 的参数

2. 使用 `core.plugin.handler` 的子装饰器

   这种方式比第一种简单, 不需要声明 `handler` 的类型

   ```python
   from core.plugin import Plugin, handler
   from telegram import Update
   from telegram.ext import CallbackContext
   
   
   class TestPlugin(Plugin):
       @handler.command(command='start', block=False)
       async def start(self, update: Update, context: CallbackContext):
           await update.effective_chat.send_message('hello world!')
   ```

### 对于 `ConversationHandler`

由于 `ConversationHandler` 比较特殊，所以**一个 Plugin 类中只能存在一个 `ConversationHandler`**

`conversation.entry_point` 、`conversation.state` 和 `conversation.fallback` 装饰器分别对应
`ConversationHandler` 的 `entry_points`、`stats` 和 `fallbacks` 参数

```python
from telegram import Update
from telegram.ext import CallbackContext, filters

from core.plugin import Plugin, conversation, handler

STATE_A, STATE_B, STATE_C = range(3)


class TestConversation(Plugin.Conversation, allow_reentry=True, block=False):

    @conversation.entry_point  # 标注这个handler是ConversationHandler的一个entry_point
    @handler.command(command='entry')
    async def entry_point(self, update: Update, context: CallbackContext):
        """do something"""

    @conversation.state(state=STATE_A)
    @handler.message(filters=filters.TEXT)
    async def state(self, update: Update, context: CallbackContext):
        """do something"""

    @conversation.fallback
    @handler.message(filters=filters.TEXT)
    async def fallback(self, update: Update, context: CallbackContext):
        """do something"""

    @handler.inline_query()  # 你可以在此 Plugin 下定义其它类型的 handler
    async def inline_query(self, update: Update, context: CallbackContext):
        """do something"""

```

## 关于 `Service`

服务 `Service` 需定义在 `services` 文件夹下, 并继承 `core.service.Service`

每个 `Service` 都应包含 `start` 和 `stop` 方法, 且这两个方法都为异步方法

```python
from core.service import Service


class TestService(Service):
    def __init__(self):
        """do something"""

    async def start(self, *args, **kwargs):
        """do something"""

    async def stop(self, *args, **kwargs):
        """do something"""
```