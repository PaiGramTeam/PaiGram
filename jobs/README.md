# jobs 目录

## 说明

改目录存放 BOT 的工作队列呸注册和具体实现

## 基础代码

``` python
import datetime

from telegram.ext import CallbackContext

from jobs.base import RunDailyHandler
from logger import Log
from manager import listener_jobs_class


@listener_jobs_class()
class JobTest:

    @classmethod
    def build_jobs(cls) -> list:
        test = cls()
        # 注册每日执行任务
        # 执行时间为21点45分
        return [
            RunDailyHandler(test.test, datetime.time(21, 45, 00), name="测试Job")
        ]

    async def test(self, context: CallbackContext):
        Log.info("测试Job[OK]")
```

### 注意

jobs 模块下的类必须提供 `build_jobs` 类方法作为构建相应处理程序给 `handle.py`

只需在构建的类前加上 `@listener_jobs_class()` 修饰器即可