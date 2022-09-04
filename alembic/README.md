# alembic 目录

## 说明

该目录包含 [SQLAlchemy](https://www.sqlalchemy.org/) 数据库版本管理工具 [alembic](https://alembic.sqlalchemy.org/) 的迁移脚本（migrations）。

这里数据库版本指的是本项目的数据库表结构，并不是 MySQL 版本。

## 常用功能

### 1. 升级版本

拉取代码以后，如果发现有新的 `alembic/versions/xxxxxxx.py`，执行命令进行数据库迁移。

``` shell
# 检查将要执行的 SQL
alembic upgrade head --sql
# 执行升级 SQL
alembic upgrade head
```

### 2. 创建一个迁移版本（自动）

新增或修改 Model 以后运行下面的命令，alembic 将自动比较 model 定义和本地数据库的差异，然后创建一个新的迁移脚本

```python
# 举例：新增 Model
class User(SQLModel, table=True):
    __table_args__ = dict(mysql_charset='utf8mb4', mysql_collate="utf8mb4_general_ci")

    id: int = Field(primary_key=True)
    name: str = Field()
```

``` shell
# 引号内是本次迁移的名字，类似 git commit message 请保持可读性
alembic revision --autogenerate -m "add_xxx_to_xxx_table"
```

创建以后，可以使用 `black` 或其他工具格式化迁移脚本，然后执行升级

### 3. 创建一个迁移版本（手动）

手动写迁移脚本，一般用于修改数据的情况，比如新增了一个字段，需要从其他表把数据读到新字段里。

``` shell
alembic revision -m "add_xxx_to_xxx_table"
```

> 通常情况下，如果上线后升级版本出错，不建议使用数据库降级命令，数据库降级难以管理，建议另外写一个迁移脚本进行手动降级
