from typing import Optional, Dict

from core.services.devices import DevicesService
from modules.apihelper.utility.helpers import get_device_id, hex_digest


class DevicesMethods:
    def __init__(self):
        self.service: Optional[DevicesService] = None

    @staticmethod
    def get_default_device_header(account_id: int, headers: Dict = None) -> Dict[str, str]:
        headers = headers or {}
        headers["x-rpc-device_id"] = get_device_id(str(account_id))
        headers["x-rpc-device_fp"] = hex_digest(headers["x-rpc-device_id"])[:13]
        headers["x-rpc-device_name"] = "Xiaomi"
        return headers

    async def update_device_headers(self, account_id: int, headers: Dict = None) -> Dict[str, str]:
        account_id = account_id or 0
        if not self.service:
            return self.get_default_device_header(account_id, headers)
        device = await self.service.get(account_id)
        if not device:
            return self.get_default_device_header(account_id, headers)
        headers = headers or {}
        headers["x-rpc-device_id"] = device.device_id
        headers["x-rpc-device_fp"] = device.device_fp
        headers["x-rpc-device_name"] = device.device_name or "Xiaomi"
        return headers


devices_methods = DevicesMethods()
