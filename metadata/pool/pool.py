from metadata.pool.pool_100 import POOL_100
from metadata.pool.pool_200 import POOL_200
from metadata.pool.pool_301 import POOL_301
from metadata.pool.pool_302 import POOL_302
from metadata.pool.pool_500 import POOL_500
from metadata.pool.pool_1000 import POOL_1000
from metadata.pool.pool_2000 import POOL_2000


def get_pool_by_id(pool_type):
    if pool_type == 100:
        return POOL_100
    if pool_type == 200:
        return POOL_200
    if pool_type in [301, 400]:
        return POOL_301
    if pool_type == 302:
        return POOL_302
    if pool_type == 500:
        return POOL_500
    if pool_type == 1000:
        return POOL_1000
    if pool_type == 2000:
        return POOL_2000
    return None
