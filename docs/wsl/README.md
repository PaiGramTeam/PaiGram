# WSL2 Ubuntu 22.04 部署

[en documentation](en.md)

## 前置条件

- 安装 WSL2 (Ubuntu 22.04 LTS) - `微软应用商店` -> `Ubuntu 22.04 LTS`
- 运行 Ubuntu 22.04 - `开始` -> 搜索`Ubuntu 22.04 LTS`
- 设置用户名/密码
- 确认环境 (输出相似即可)
  ```
  $ uname -a
  Linux lightning 5.10.16.3-microsoft-standard-WSL2 #1 SMP Fri Apr 2 22:23:49 UTC 2021 x86_64 x86_64 x86_64 GNU/Linux
  $ python3 --version
  Python 3.10.6
  ```

## 系统依赖

- 安装redis、pip
  ```
  $ sudo apt update
  ...
  $ sudo apt install redis-server python3-pip python3-venv
  ```
- 确认redis是否成功运行
  ```
  $ redis-cli
  Could not connect to Redis at 127.0.0.1:6379: Connection refused
  not connected>
  ```
- 修改 `/etc/redis/redis.conf`, 注释掉 `supervised no`, 添加 `supervised systemd`
  ```
  #supervised no
  supervised systemd
  ```
- 运行 `redis-server`
  ```
  $ sudo service redis-server start
  Starting redis-server: redis-server.
  $ 
  ```
- 再次确认redis是否成功运行
  ```
  $ redis-cli
  127.0.0.1:6379> SELECT 0
  OK
  127.0.0.1:6379>
  ```

## clone PaiGram 项目

- 克隆项目
  ```
  $ git clone git@github.com:PaiGramTeam/PaiGram.git
  ...
  $ cd PaiGram/
  ~/PaiGram $
  ```

## 项目配置
- 配置虚拟环境
  ```
  ~/PaiGram $ python3 -m venv venv
  ~/PaiGram $ source venv/bin/activate
  (venv) ~/PaiGram $
  ```
- 安装依赖
  ```
  (venv) ~/PaiGram $ pip install poetry
  Collecting poetry 
  ...
  (venv) ~/PaiGram $ poetry install --extras all
  Installing dependencies from lock file
  Package operations: 88 installs, 3 updates, 0 removals 
  ...
  (venv) ~/PaiGram $ playwright install chromium
  Downloading Chromium 107.0.5304.18 (playwright build v1028) - 137.8 Mb [====================] 100% 0.0s
  Chromium 107.0.5304.18 (playwright build v1028) downloaded to /home/username/.cache/ms-playwright/chromium-1028 
  (venv) ~/PaiGram $ playwright install-deps chromium
  ...
  (venv) ~/PaiGram $
  ```
- 安装chromium依赖
  ```
  sudo apt-get install libnss3\
    libnspr4\
    libatk1.0-0\
    libatk-bridge2.0-0\
    libcups2\
    libatspi2.0-0\
    libxcomposite1\
    libxdamage1\
    libxfixes3\
    libxrandr2\
    libgbm1\
    libxkbcommon0\
    libpango-1.0-0\
    libcairo2\
    libasound2\
    libwayland-client0
  ```
- 修改项目配置 (`.env`)
  ```
  (venv) ~/PaiGram $ cp .env.example .env
  (venv) ~/PaiGram $
  ```
- 修改 `.env` 文件 (示例用的是sqlite, 数据库文件名`db.sqlite3`):
  ```
  DB_DRIVER_NAME=sqlite+aiosqlite
  DB_DATABASE=db.sqlite3
  ```
- 运行alembic自动建表
  ```
  (venv) ~/PaiGram $ alembic upgrade head
  INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
  INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
  INFO  [alembic.runtime.migration] Running upgrade  -> 9e9a36470cd5, init
  INFO  [alembic.runtime.migration] Running upgrade 9e9a36470cd5 -> ddcfba3c7d5c, v4
  (venv) ~/PaiGram $
  ```
  
## 运行项目

```
(venv) ~/PaiGram $ python3 run.py
[2023-04-30 09:56:07] INFO     正在启动 BOT 中...                                                                                                                                  core.application 134  
[2023-04-30 09:56:08] INFO     Telegram 初始化成功                                                                                                                                 core.application 141  
                      INFO     正在尝试启动 Playwright                                                                                                                   core.dependence.aiobrowser 31   
[2023-04-30 09:56:09] SUCCESS  Playwright 启动成功                                                                                                                       core.dependence.aiobrowser 33   
                      INFO     正在尝试启动 Browser                                                                                                                      core.dependence.aiobrowser 35   
                      SUCCESS  Browser 启动成功                                                                                                                          core.dependence.aiobrowser 38   
                      SUCCESS  基础服务 "AioBrowser" 启动成功                                                                                                                          core.manager 97   
                      SUCCESS  基础服务 "Database" 启动成功                                                                                                                            core.manager 97   
                      INFO     正在尝试建立与 Redis 连接                                                                                                                    core.dependence.redisdb 39   
                      INFO     连接 Redis 成功                                                                                                                              core.dependence.redisdb 29   
                      SUCCESS  基础服务 "RedisDB" 启动成功                                                                                                                             core.manager 97   
                      INFO     正在刷新元数据                                                                                                                                core.dependence.assets 538  
[2023-04-30 09:56:21] SUCCESS  Avatar data is done.                                                                                                                          metadata.scripts.honey 173  
[2023-04-30 09:56:24] SUCCESS  Weapon data is done.                                                                                                                          metadata.scripts.honey 175  
[2023-04-30 09:56:30] SUCCESS  Material data is done.                                                                                                                        metadata.scripts.honey 177  
[2023-04-30 09:57:14] SUCCESS  Artifact data is done.                                                                                                                        metadata.scripts.honey 179  
[2023-04-30 09:57:20] SUCCESS  Namecard data is done.                                                                                                                        metadata.scripts.honey 181  
                      INFO     刷新元数据成功                                                                                                                                core.dependence.assets 543  
                      SUCCESS  基础服务 "AssetsService" 启动成功                                                                                                                       core.manager 97   
                      INFO     MTProto 服务需要的 api_id 未配置 本次服务 client 为 None                                                                                     core.dependence.mtproto 51   
                      SUCCESS  基础服务 "MTProto" 启动成功                                                                                                                             core.manager 97   
                      SUCCESS  服务 "SignServices" 启动成功                                                                                                                            core.manager 189  
                      SUCCESS  服务 "WikiService" 启动成功                                                                                                                             core.manager 189  
                      SUCCESS  服务 "UserService" 启动成功                                                                                                                             core.manager 189  
                      WARNING  检测到未配置Bot所有者 会导无法正常使用管理员权限                                                                                        core.services.users.services 51   
                      SUCCESS  服务 "UserAdminService" 启动成功                                                                                                                        core.manager 189  
                      SUCCESS  服务 "TemplateService" 启动成功                                                                                                                         core.manager 189  
                      SUCCESS  服务 "QuizService" 启动成功                                                                                                                             core.manager 189  
                      SUCCESS  服务 "PlayersService" 启动成功                                                                                                                          core.manager 189  
                      SUCCESS  服务 "PlayerInfoService" 启动成功                                                                                                                       core.manager 189  
                      SUCCESS  服务 "GameStrategyService" 启动成功                                                                                                                     core.manager 189  
                      SUCCESS  服务 "CookiesService" 启动成功                                                                                                                          core.manager 189  
                      INFO     正在初始化公共Cookies池                                                                                                               core.services.cookies.services 47   
                      SUCCESS  刷新公共Cookies池成功                                                                                                                 core.services.cookies.services 49   
                      SUCCESS  服务 "PublicCookiesService" 启动成功                                                                                                                    core.manager 189  
                      SUCCESS  服务 "SearchServices" 启动成功                                                                                                                          core.manager 189  
[2023-04-30 09:57:21] SUCCESS  插件 "plugins.jobs.public_cookies.PublicCookiesPlugin" 安装成功                                                                                         core.manager 273  
                      INFO     正在创建角色详细信息表                                                                                                                         plugins.tools.genshin 70   
                      SUCCESS  创建角色详细信息表成功                                                                                                                         plugins.tools.genshin 73   
                      SUCCESS  插件 "plugins.tools.genshin.CharacterDetails" 安装成功                                                                                                  core.manager 273  
                      SUCCESS  插件 "plugins.tools.genshin.GenshinHelper" 安装成功                                                                                                     core.manager 273  
                      SUCCESS  插件 "plugins.tools.sign.SignSystem" 安装成功                                                                                                           core.manager 273  
                      SUCCESS  插件 "plugins.genshin.sign.Sign" 安装成功                                                                                                               core.manager 273  
                      SUCCESS  插件 "plugins.jobs.sign.SignJob" 安装成功                                                                                                               core.manager 273  
                      SUCCESS  插件 "plugins.genshin.hilichurls.HilichurlsPlugin" 安装成功                                                                                             core.manager 273  
                      SUCCESS  插件 "plugins.genshin.avatar_list.AvatarListPlugin" 安装成功                                                                                            core.manager 273  
                      SUCCESS  插件 "plugins.genshin.wish.WishSimulatorPlugin" 安装成功                                                                                                core.manager 273  
                      SUCCESS  插件 "plugins.genshin.abyss_team.AbyssTeamPlugin" 安装成功                                                                                              core.manager 273  
                      SUCCESS  插件 "plugins.genshin.strategy.StrategyPlugin" 安装成功                                                                                                 core.manager 273  
                      SUCCESS  插件 "plugins.genshin.stats.PlayerStatsPlugins" 安装成功                                                                                                core.manager 273  
                      SUCCESS  插件 "plugins.genshin.player_cards.PlayerCards" 安装成功                                                                                                core.manager 273  
                      SUCCESS  插件 "plugins.genshin.help.HelpPlugin" 安装成功                                                                                                         core.manager 273  
                      SUCCESS  插件 "plugins.genshin.ledger.LedgerPlugin" 安装成功                                                                                                     core.manager 273  
                      SUCCESS  插件 "plugins.genshin.reg_time.RegTimePlugin" 安装成功                                                                                                  core.manager 273  
                      SUCCESS  插件 "plugins.genshin.daily.material.DailyMaterial" 安装成功                                                                                            core.manager 273 
                      ...
```