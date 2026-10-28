import hashlib
import json
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from shower_service.exceptions import (
    PaymentProviderUnavailableError,
    ShowerBusyError,
    ShowerUnavailableError,
)
from shower_service.payments import PaymentClient
from shower_service.shelly import ShellyClient


class FakeResponse:
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


class PaymentClientTest(unittest.TestCase):
    def setUp(self):
        self.client = PaymentClient(
            merchant_id=123,
            pos_id=123,
            api_key="api-key",
            crc="crc-secret",
            base_url="https://payments.example.com",
        )

    def test_register_signature_matches_provider_format(self):
        expected_payload = (
            '{"sessionId":"session-id",'
            '"merchantId":123,'
            '"amount":1500,'
            '"currency":"PLN",'
            '"crc":"crc-secret"}'
        )
        expected = hashlib.sha384(expected_payload.encode()).hexdigest()

        self.assertEqual(
            expected,
            self.client._register_signature("session-id", 1500),
        )

    def test_verify_signature_matches_provider_format(self):
        expected_payload = (
            '{"sessionId":"session-id",'
            '"orderId":456,'
            '"amount":1500,'
            '"currency":"PLN",'
            '"crc":"crc-secret"}'
        )
        expected = hashlib.sha384(expected_payload.encode()).hexdigest()

        self.assertEqual(
            expected,
            self.client._verify_signature(
                {"sessionId": "session-id", "orderId": 456, "amount": 1500}
            ),
        )

    def test_verification_timeout_is_retryable(self):
        def failing_opener(*_args, **_kwargs):
            raise urllib.error.URLError("timeout")

        client = PaymentClient(
            merchant_id=123,
            pos_id=123,
            api_key="api-key",
            crc="crc-secret",
            base_url="https://payments.example.com",
            opener=failing_opener,
        )

        with self.assertRaises(PaymentProviderUnavailableError):
            client.verify({"sessionId": "session-id", "orderId": 456, "amount": 1500})


class ShellyClientTest(unittest.TestCase):
    def test_available_device_passes_check(self):
        def opener(*_args, **_kwargs):
            return FakeResponse([{"online": True, "status": {"switch:0": {"output": False}}}])

        ShellyClient("auth", "device", opener=opener).ensure_available()

    def test_active_device_is_reported_as_busy(self):
        def opener(*_args, **_kwargs):
            return FakeResponse([{"online": True, "status": {"switch:0": {"output": True}}}])

        with self.assertRaises(ShowerBusyError):
            ShellyClient("auth", "device", opener=opener).ensure_available()

    def test_offline_device_is_reported_as_unavailable(self):
        def opener(*_args, **_kwargs):
            return FakeResponse([{"online": False, "status": {}}])

        with self.assertRaises(ShowerUnavailableError):
            ShellyClient("auth", "device", opener=opener).ensure_available()

    def test_network_failure_is_reported_as_unavailable(self):
        def failing_opener(*_args, **_kwargs):
            raise TimeoutError

        with self.assertRaises(ShowerUnavailableError):
            ShellyClient("auth", "device", opener=failing_opener).ensure_available()


if __name__ == "__main__":
    unittest.main()
