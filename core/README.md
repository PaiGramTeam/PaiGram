# core 目录说明

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