import json
import urllib.request

from .exceptions import ShowerBusyError, ShowerUnavailableError
from .logging import log


class ShellyClient:
    def __init__(self, auth_key: str, device_id: str, opener=urllib.request.urlopen):
        self._auth_key = auth_key
        self._device_id = device_id
        self._open = opener

    def ensure_available(self) -> None:
        request = urllib.request.Request(
            f"https://shelly-253-eu.shelly.cloud/v2/devices/api/get?auth_key={self._auth_key}",
            data=json.dumps({"ids": [self._device_id], "select": ["status"]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._open(request, timeout=5) as response:
                body = json.loads(response.read().decode())
        except Exception as error:
            log("Shelly status check failed", {"errorType": type(error).__name__})
            raise ShowerUnavailableError("Nie udało się połączyć z urządzeniem") from error

        device = body[0] if isinstance(body, list) and body else None
        if not device:
            raise ShowerUnavailableError("Urządzenie nie zostało znalezione")
        if not device.get("online"):
            raise ShowerUnavailableError("Urządzenie jest niedostępne")
        output = device.get("status", {}).get("switch:0", {}).get("output")
        if output is None:
            raise ShowerUnavailableError("Nie udało się odczytać stanu urządzenia")
        if output:
            raise ShowerBusyError("Prysznic jest aktualnie używany")

    def activate(self) -> None:
        request = urllib.request.Request(
            f"https://shelly-253-eu.shelly.cloud/v2/devices/api/set/switch?auth_key={self._auth_key}",
            data=json.dumps({"id": self._device_id, "on": True}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._open(request, timeout=5) as response:
                response.read()
            log("Shower activated", {"deviceId": self._device_id})
        except Exception as error:
            log("Shower activation failed", {"errorType": type(error).__name__})
            raise ShowerUnavailableError("Nie udało się uruchomić urządzenia") from error
