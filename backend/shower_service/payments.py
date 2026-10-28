import base64
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

from .exceptions import PaymentProviderUnavailableError
from .logging import log


class PaymentClient:
    def __init__(self, merchant_id, pos_id, api_key, crc, base_url, opener=urllib.request.urlopen):
        self._merchant_id = merchant_id
        self._pos_id = pos_id
        self._api_key = api_key
        self._crc = crc
        self._base_url = base_url
        self._open = opener

    def register(self, session_id, amount, customer_email, return_url, status_url, description):
        payload = {
            "merchantId": self._merchant_id,
            "posId": self._pos_id,
            "sessionId": session_id,
            "amount": amount,
            "currency": "PLN",
            "description": description,
            "email": customer_email,
            "country": "PL",
            "language": "pl",
            "channel": 16,
            "waitForResult": False,
            "urlReturn": return_url,
            "urlStatus": status_url,
            "sign": self._register_signature(session_id, amount),
        }
        request = urllib.request.Request(
            f"{self._base_url}/api/v1/transaction/register",
            data=urllib.parse.urlencode(payload).encode(),
            headers=self._headers("application/x-www-form-urlencoded"),
            method="POST",
        )
        with self._open(request, timeout=10) as response:
            body = json.loads(response.read().decode())
        return f"{self._base_url}/trnRequest/{body['data']['token']}"

    def verify(self, data: dict) -> bool:
        payload = {
            "merchantId": self._merchant_id,
            "posId": self._pos_id,
            "sessionId": data["sessionId"],
            "amount": data["amount"],
            "currency": "PLN",
            "orderId": data["orderId"],
            "sign": self._verify_signature(data),
        }
        request = urllib.request.Request(
            f"{self._base_url}/api/v1/transaction/verify",
            data=json.dumps(payload).encode(),
            headers=self._headers("application/json"),
            method="PUT",
        )
        try:
            with self._open(request, timeout=10) as response:
                body: dict[str, Any] = json.loads(response.read().decode())
            status = body.get("data", {}).get("status")
            return cast(bool, status == "success")
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500:
                log("Payment verification rejected", {"statusCode": error.code})
                return False
            raise PaymentProviderUnavailableError("Payment provider unavailable") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as error:
            raise PaymentProviderUnavailableError("Payment provider unavailable") from error

    def _headers(self, content_type: str) -> dict:
        credentials = base64.b64encode(f"{self._pos_id}:{self._api_key}".encode()).decode()
        return {"Authorization": f"Basic {credentials}", "Content-Type": content_type}

    def _register_signature(self, session_id: str, amount: int) -> str:
        return self._sha384(
            {
                "sessionId": session_id,
                "merchantId": self._merchant_id,
                "amount": amount,
                "currency": "PLN",
                "crc": self._crc,
            }
        )

    def _verify_signature(self, data: dict) -> str:
        return self._sha384(
            {
                "sessionId": data["sessionId"],
                "orderId": data["orderId"],
                "amount": data["amount"],
                "currency": "PLN",
                "crc": self._crc,
            }
        )

    @staticmethod
    def _sha384(data: dict) -> str:
        serialized = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha384(serialized.encode()).hexdigest()
