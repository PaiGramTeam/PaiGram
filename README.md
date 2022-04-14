# TGPaimonBot

## 简介

基于 
[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 
的异步测试分支的原神BOT

~~为啥用测试版本？别问，问就是我想急着用了。~~

### 其他说明

这个项目目前正在扩展，加入更多原神相关娱乐和信息查询功能，敬请期待。

## 命令
### 群验证



> 下面都是最初在同步版本的说明，现在哈子迁移

### inline命令
目前本项目最初大多数基于 [inline](https://core.telegram.org/bots/inline) 为主的命令。
在聊天框输入对应的机器人名称，
如官方的贴纸机器人 `@Stickers` 在选择贴纸的时候，按钮会拉起inline，十分方便选择要修改的贴纸。

### 命令列表
|      Quite       | Return                                     |
|:----------------:|--------------------------------------------|
| 对应的角色名称（如 `胡桃` ） | 角色相关信息                                     |
|    输入 `抽卡模拟器`    | 启动抽卡模拟器，以10发进行计算，后面加上数字（并用空格分开）可进行自定义的许愿次数 |


### 关于inline命令

#### inline命令带来的好处

无需把BOT拉进群，在输入框输入BOT名称即可使用。

#### inline命令带来的限制

用户输入的信息`Quite`后10S内机器人必须处理完毕，否则会抛出
`telegram.error.BadRequest: Query is too old and response timeout expired or query id is invalid`
错误。

而且返回图片时只能传递图片连接，不能传递 `bytes` 。

## Thanks
|                       Nickname                        | Contribution     |
|:-----------------------------------------------------:|------------------|
| [原神抽卡全机制总结](https://www.bilibili.com/read/cv10468091) | 本项目抽卡模拟器使用的逻辑    |
|  [西风驿站](https://bbs.mihoyo.com/ys/collection/307224)  | 本项目攻略图图源         |
|  [Yunzai-Bot](https://github.com/Le-niao/Yunzai-Bot)  | 本项使用的抽卡图片和前端资源来源 |