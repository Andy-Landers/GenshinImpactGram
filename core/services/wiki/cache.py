import ujson as json

from core.base_service import BaseService
from core.dependence.redisdb import RedisDB
from modules.wiki.base import Model

__all__ = ["WikiCache"]


class WikiCache(BaseService.Component):
    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "wiki"

    async def set(self, key: str, value):
        qname = f"{self.qname}:{key}"
        if isinstance(value, Model):
            value = value.json()
        elif isinstance(value, (dict, list)):
            value = json.dumps(value)
        await self.client.set(qname, value)

    async def delete(self, key: str):
        qname = f"{self.qname}:{key}"
        await self.client.delete(qname)

    async def get(self, key: str) -> dict:
        qname = f"{self.qname}:{key}"
        # noinspection PyBroadException
        try:
            result = json.loads(await self.client.get(qname))
        except Exception:  # pylint: disable=W0703
            result = []
        if isinstance(result, list) and len(result) > 0:
            for num, item in enumerate(result):
                result[num] = json.loads(item)
        return result
