import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from shower_service.config import Settings
from shower_service.exceptions import ShowerBusyError
from shower_service.service import ShowerService


class ShowerServiceTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            shelly_auth_key="secret",
            device_id="device",
            p24_merchant_id=1,
            p24_pos_id=1,
            p24_api_key="secret",
            p24_crc="secret",
            payment_base_url="https://payments.example.com",
            amount=1500,
            dynamodb_table="sessions",
            frontend_base_url="https://frontend.example.com",
            public_api_base_url="https://api.example.com",
        )
        self.payments = Mock()
        self.shelly = Mock()
        self.sessions = Mock()
        self.service = ShowerService(
            self.settings,
            self.payments,
            self.shelly,
            self.sessions,
            clock=lambda: 1_000,
        )

    @patch("shower_service.service.uuid.uuid4", return_value="session-id")
    def test_create_payment_checks_device_and_stores_session(self, _uuid):
        self.payments.register.return_value = "https://payments.example.com/redirect"
        self.sessions.reserve_device.return_value = True

        result = self.service.create_payment("demo@example.com")

        self.assertEqual("https://payments.example.com/redirect", result)
        self.shelly.ensure_available.assert_called_once_with()
        self.sessions.reserve_device.assert_called_once_with(
            "device",
            "session-id",
            1_000,
            1_900,
        )
        self.payments.register.assert_called_once_with(
            session_id="session-id",
            amount=1500,
            customer_email="demo@example.com",
            return_url="https://frontend.example.com/waiting.html?sessionId=session-id",
            status_url="https://api.example.com/webhook",
            description="Prysznic portowy nr 1, 6 minut",
        )
        self.sessions.create_pending.assert_called_once_with(
            session_id="session-id",
            device_id="device",
            amount=1500,
            customer_email="demo@example.com",
            expires_at=87_400,
        )

    @patch("shower_service.service.uuid.uuid4", return_value="activation-token")
    def test_verified_webhook_claims_session_and_activates_shower(self, _uuid):
        payload = {"sessionId": "session-id", "orderId": 123, "amount": 1500}
        self.payments.verify.return_value = True
        self.sessions.get.return_value = {"status": "pending", "amount": 1500}
        self.sessions.extend_device_reservation.return_value = True
        self.sessions.claim_activation.return_value = True

        self.service.process_webhook(payload)

        self.sessions.extend_device_reservation.assert_called_once_with(
            "device", "session-id", 1_360
        )
        self.sessions.claim_activation.assert_called_once_with(
            session_id="session-id",
            activation_token="activation-token",
            now=1_000,
            lease_until=1_030,
        )
        self.shelly.activate.assert_called_once_with()
        self.sessions.mark_active.assert_called_once_with(
            session_id="session-id",
            activation_token="activation-token",
            shower_ends_at=1_360,
            expires_at=4_960,
        )

    def test_duplicate_webhook_does_not_activate_shower_again(self):
        payload = {"sessionId": "session-id", "orderId": 123, "amount": 1500}
        self.payments.verify.return_value = True
        self.sessions.get.return_value = {"status": "active", "amount": 1500}

        self.service.process_webhook(payload)

        self.sessions.claim_activation.assert_not_called()
        self.shelly.activate.assert_not_called()

    def test_failed_verification_does_not_activate_shower(self):
        self.payments.verify.return_value = False
        self.sessions.get.return_value = {"status": "pending", "amount": 1500}

        self.service.process_webhook({"sessionId": "session-id", "orderId": 123, "amount": 1500})

        self.sessions.get.assert_called_once_with("session-id")
        self.shelly.activate.assert_not_called()

    @patch("shower_service.service.uuid.uuid4", return_value="session-id")
    def test_payment_registration_failure_releases_device(self, _uuid):
        self.sessions.reserve_device.return_value = True
        self.payments.register.side_effect = TimeoutError

        with self.assertRaises(TimeoutError):
            self.service.create_payment("demo@example.com")

        self.sessions.mark_registration_failed.assert_called_once_with("session-id", 4_600)
        self.sessions.release_device.assert_called_once_with("device", "session-id")

    def test_existing_device_reservation_blocks_new_payment(self):
        self.sessions.reserve_device.return_value = False

        with self.assertRaises(ShowerBusyError):
            self.service.create_payment("demo@example.com")

        self.payments.register.assert_not_called()
        self.sessions.create_pending.assert_not_called()

    def test_webhook_amount_mismatch_is_not_verified_or_activated(self):
        self.sessions.get.return_value = {"status": "pending", "amount": 1500}

        self.service.process_webhook({"sessionId": "session-id", "orderId": 123, "amount": 999})

        self.payments.verify.assert_not_called()
        self.sessions.claim_activation.assert_not_called()
        self.shelly.activate.assert_not_called()

    @patch("shower_service.service.uuid.uuid4", return_value="activation-token")
    def test_activation_failure_is_recorded_and_re_raised(self, _uuid):
        payload = {"sessionId": "session-id", "orderId": 123, "amount": 1500}
        self.payments.verify.return_value = True
        self.sessions.get.return_value = {"status": "pending", "amount": 1500}
        self.sessions.extend_device_reservation.return_value = True
        self.sessions.claim_activation.return_value = True
        self.shelly.activate.side_effect = TimeoutError

        with self.assertRaises(TimeoutError):
            self.service.process_webhook(payload)

        self.sessions.mark_activation_failed.assert_called_once_with(
            session_id="session-id",
            activation_token="activation-token",
            expires_at=4_600,
        )


if __name__ == "__main__":
    unittest.main()
