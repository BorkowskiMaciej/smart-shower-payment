import json
import re
from decimal import Decimal

from .exceptions import (
    DeviceReservationLostError,
    PaymentProviderUnavailableError,
    ShowerBusyError,
    ShowerUnavailableError,
)
from .logging import log

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DecimalEncoder(json.JSONEncoder):
    def default(self, value):
        if isinstance(value, Decimal):
            return int(value) if value % 1 == 0 else float(value)
        return super().default(value)


class ApiHandler:
    def __init__(self, service, frontend_origin: str):
        self._service = service
        self._frontend_origin = frontend_origin

    def handle(self, event: dict, _context) -> dict:
        path = event.get("rawPath", "")
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        log("Request received", {"path": path, "method": method})
        if method == "OPTIONS":
            return self._response(204)
        if path == "/create-payment" and method == "POST":
            return self._create_payment(event)
        if path == "/webhook" and method == "POST":
            return self._webhook(event)
        if path == "/status" and method == "GET":
            return self._status(event)
        return self._response(404, "Not found")

    def _create_payment(self, event: dict) -> dict:
        try:
            body = self._json_body(event)
        except (json.JSONDecodeError, TypeError):
            return self._json_response(400, {"error": "Invalid JSON body"})
        email = body.get("email")
        if not isinstance(email, str) or not EMAIL_PATTERN.fullmatch(email):
            return self._json_response(400, {"error": "Invalid email parameter"})
        try:
            return self._json_response(200, {"redirectUrl": self._service.create_payment(email)})
        except ShowerBusyError as error:
            return self._json_response(409, {"error": "shower_busy", "message": str(error)})
        except ShowerUnavailableError as error:
            return self._json_response(503, {"error": "shower_unavailable", "message": str(error)})
        except Exception as error:
            log("Payment creation failed", {"errorType": type(error).__name__})
            return self._json_response(500, {"error": "Internal error"})

    def _webhook(self, event: dict) -> dict:
        try:
            body = self._json_body(event)
            if not all(key in body for key in ("sessionId", "orderId", "amount")):
                return self._json_response(400, {"error": "Invalid webhook payload"})
            self._service.process_webhook(body)
        except (json.JSONDecodeError, TypeError):
            return self._json_response(400, {"error": "Invalid JSON body"})
        except (
            PaymentProviderUnavailableError,
            ShowerUnavailableError,
            DeviceReservationLostError,
        ) as error:
            log("Webhook processing deferred", {"errorType": type(error).__name__})
            return self._json_response(503, {"error": "Processing temporarily unavailable"})
        except Exception as error:
            log("Webhook processing failed", {"errorType": type(error).__name__})
            return self._json_response(500, {"error": "Internal error"})
        return self._response(200, "OK")

    def _status(self, event: dict) -> dict:
        session_id = (event.get("queryStringParameters") or {}).get("sessionId")
        if not session_id:
            return self._json_response(400, {"error": "Missing sessionId"})
        try:
            status = self._service.get_status(session_id)
            if status is None:
                return self._json_response(404, {"status": "not_found"})
            return self._json_response(200, status)
        except Exception as error:
            log("Status lookup failed", {"errorType": type(error).__name__})
            return self._json_response(500, {"error": "Internal error"})

    @staticmethod
    def _json_body(event: dict) -> dict:
        body = json.loads(event.get("body") or "{}")
        if not isinstance(body, dict):
            raise TypeError("JSON body must be an object")
        return body

    def _json_response(self, status_code: int, body: dict) -> dict:
        return self._response(status_code, json.dumps(body, cls=DecimalEncoder), "application/json")

    def _response(self, status_code: int, body: str = "", content_type: str = "text/plain") -> dict:
        return {
            "statusCode": status_code,
            "headers": {
                "Access-Control-Allow-Origin": self._frontend_origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Type": content_type,
            },
            "body": body,
        }
