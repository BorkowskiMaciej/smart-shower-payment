import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from shower_service.exceptions import ShowerBusyError, ShowerUnavailableError
from shower_service.handler import ApiHandler


class ApiHandlerTest(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.handler = ApiHandler(self.service, "https://frontend.example.com")

    @staticmethod
    def event(path, method, body=None, query=None):
        return {
            "rawPath": path,
            "requestContext": {"http": {"method": method}},
            "body": body,
            "queryStringParameters": query,
        }

    def test_post_creates_payment_from_json_body(self):
        self.service.create_payment.return_value = "https://payments.example.com/redirect"

        response = self.handler.handle(
            self.event(
                "/create-payment",
                "POST",
                json.dumps({"email": "demo@example.com"}),
            ),
            None,
        )

        self.assertEqual(200, response["statusCode"])
        self.assertEqual(
            "https://payments.example.com/redirect",
            json.loads(response["body"])["redirectUrl"],
        )
        self.service.create_payment.assert_called_once_with("demo@example.com")

    def test_get_does_not_create_payment(self):
        response = self.handler.handle(self.event("/create-payment", "GET"), None)

        self.assertEqual(404, response["statusCode"])
        self.service.create_payment.assert_not_called()

    def test_invalid_json_is_rejected(self):
        response = self.handler.handle(self.event("/create-payment", "POST", "not-json"), None)

        self.assertEqual(400, response["statusCode"])
        self.service.create_payment.assert_not_called()

    def test_invalid_email_is_rejected(self):
        response = self.handler.handle(
            self.event("/create-payment", "POST", json.dumps({"email": "invalid"})),
            None,
        )

        self.assertEqual(400, response["statusCode"])
        self.service.create_payment.assert_not_called()

    def test_busy_shower_returns_conflict(self):
        self.service.create_payment.side_effect = ShowerBusyError("busy")

        response = self.handler.handle(
            self.event(
                "/create-payment",
                "POST",
                json.dumps({"email": "demo@example.com"}),
            ),
            None,
        )

        self.assertEqual(409, response["statusCode"])
        self.assertEqual("shower_busy", json.loads(response["body"])["error"])

    def test_unavailable_shower_returns_service_unavailable(self):
        self.service.create_payment.side_effect = ShowerUnavailableError("offline")

        response = self.handler.handle(
            self.event(
                "/create-payment",
                "POST",
                json.dumps({"email": "demo@example.com"}),
            ),
            None,
        )

        self.assertEqual(503, response["statusCode"])

    def test_valid_webhook_is_forwarded_to_service(self):
        payload = {"sessionId": "session", "orderId": 123, "amount": 1500}

        response = self.handler.handle(self.event("/webhook", "POST", json.dumps(payload)), None)

        self.assertEqual(200, response["statusCode"])
        self.service.process_webhook.assert_called_once_with(payload)

    def test_webhook_processing_failure_requests_retry(self):
        self.service.process_webhook.side_effect = ShowerUnavailableError("offline")
        payload = {"sessionId": "session", "orderId": 123, "amount": 1500}

        response = self.handler.handle(self.event("/webhook", "POST", json.dumps(payload)), None)

        self.assertEqual(503, response["statusCode"])

    def test_status_returns_session_data(self):
        self.service.get_status.return_value = {
            "status": "paid",
            "showerEndsAt": 123456,
        }

        response = self.handler.handle(
            self.event("/status", "GET", query={"sessionId": "session"}), None
        )

        self.assertEqual(200, response["statusCode"])
        self.assertEqual("paid", json.loads(response["body"])["status"])

    def test_cors_preflight_uses_configured_origin(self):
        response = self.handler.handle(self.event("/create-payment", "OPTIONS"), None)

        self.assertEqual(204, response["statusCode"])
        self.assertEqual(
            "https://frontend.example.com",
            response["headers"]["Access-Control-Allow-Origin"],
        )


if __name__ == "__main__":
    unittest.main()
