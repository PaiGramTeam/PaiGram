from metadata.pool.pool_200 import POOL_200
from metadata.pool.pool_301 import POOL_301
from metadata.pool.pool_302 import POOL_302


def get_pool_by_id(pool_type):
    if pool_type == 200:
        return POOL_200
    if pool_type == 301:
        return POOL_301
    if pool_type == 302:
        return POOL_302
    return None
