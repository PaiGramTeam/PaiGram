import asyncio

import aiomysql

from logger import Log


class MySQL:
    def __init__(self, host: str = "127.0.0.1", port: int = 3306, user: str = "root",
                 password: str = "", database: str = "", loop=None):
        self.database = database
        self.password = password
        self.user = user
        self.port = port
        self.host = host
        self._loop = loop
        self._sql_pool = None
        Log.debug(f'获取数据库配置 [host]: {self.host}')
        Log.debug(f'获取数据库配置 [port]: {self.port}')
        Log.debug(f'获取数据库配置 [user]: {self.user}')
        Log.debug(f'获取数据库配置 [password][len]: {len(self.password)}')
        Log.debug(f'获取数据库配置 [db]: {self.database}')
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        try:
            Log.info("正在创建数据库LOOP")
            self._loop.run_until_complete(self.create_pool())
            Log.info("创建数据库LOOP成功")
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as exc:
            Log.error("创建数据库LOOP发生严重错误")
            raise exc

    async def wait_closed(self):
        if self._sql_pool is None:
            return
        pool = self._sql_pool
        pool.close()
        await pool.wait_closed()

    async def create_pool(self):
        self._sql_pool = await aiomysql.create_pool(
            host=self.host, port=self.port,
            user=self.user, password=self.password,
            db=self.database, loop=self._loop)

    async def _get_pool(self):
        if self._sql_pool is None:
            raise RuntimeError("mysql pool is none")
        return self._sql_pool

    async def executemany(self, query, query_args):
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            sql_cur = await conn.cursor()
            await sql_cur.executemany(query, query_args)
            rowcount = sql_cur.rowcount
            await sql_cur.close()
            await conn.commit()
        return rowcount

    async def execute_and_fetchall(self, query, query_args):
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            sql_cur = await conn.cursor()
            await sql_cur.execute(query, query_args)
            result = await sql_cur.fetchall()
            await sql_cur.close()
            await conn.commit()
        return result
