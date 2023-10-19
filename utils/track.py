import contextlib
import datetime
import json
import time
import uuid

from httpx import AsyncClient
from telegram import Update

from gram_core.config import config
from utils.log import logger


class DatetimeSerializer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            fmt = "%Y-%m-%dT%H:%M:%S"
            return obj.strftime(fmt)

        return json.JSONEncoder.default(self, obj)


class Mixpanel:
    def __init__(self):
        self.token = config.mixpanel_token
        self._serializer = DatetimeSerializer
        self._request = AsyncClient()
        self.api_host = "api.mixpanel.com"

    @staticmethod
    def _now():
        return time.time()

    @staticmethod
    def _make_insert_id():
        return uuid.uuid4().hex

    @staticmethod
    def json_dumps(data, cls=None):
        # Separators are specified to eliminate whitespace.
        return json.dumps(data, separators=(",", ":"), cls=cls)

    async def api_call(self, endpoint, json_message):
        _endpoints = {
            "events": f"https://{self.api_host}/track",
            "people": f"https://{self.api_host}/engage",
        }
        request_url = _endpoints.get(endpoint)
        if request_url is None:
            return
        params = {
            "data": json_message,
            "verbose": 1,
            "ip": 0,
        }
        start = self._now()
        with contextlib.suppress(Exception):
            await self._request.post(request_url, data=params, timeout=10.0)
        logger.debug(f"Mixpanel request took {self._now() - start} seconds")

    async def people_set(self, distinct_id: str, properties: dict):
        message = {
            "$distinct_id": distinct_id,
            "$set": properties,
        }
        record = {"$token": self.token, "$time": self._now()}
        # sourcery skip: dict-assign-update-to-union
        record.update(message)
        return await self.api_call("people", self.json_dumps(record, cls=self._serializer))

    async def track(self, distinct_id: str, event_name: str, properties: dict):
        all_properties = {
            "token": self.token,
            "distinct_id": distinct_id,
            "time": self._now(),
            "$insert_id": self._make_insert_id(),
            "mp_lib": "python",
            "$lib_version": "4.10.0",
        }
        if properties:
            # sourcery skip: dict-assign-update-to-union
            all_properties.update(properties)
        event = {
            "event": event_name,
            "properties": all_properties,
        }
        return await self.api_call("events", self.json_dumps(event, cls=self._serializer))

    async def track_user(self, update: Update):
        user = update.effective_user
        if user is None:
            return
        data = {"$first_name": user.first_name}
        if user.username:
            data["username"] = user.username
        await self.people_set(str(user.id), data)

    async def track_event(self, update: Update, command: str, bot_id: int):
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None:
            return
        await self.track(
            str(user.id),
            f"Function {command}",
            {"command": command, "bot_id": bot_id},
        )


mixpanel = Mixpanel()
