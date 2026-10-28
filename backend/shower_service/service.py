import time
import uuid

from .exceptions import DeviceReservationLostError, ShowerBusyError
from .logging import log


class ShowerService:
    def __init__(self, settings, payments, shelly, sessions, clock=time.time):
        self._settings = settings
        self._payments = payments
        self._shelly = shelly
        self._sessions = sessions
        self._clock = clock

    def create_payment(self, customer_email: str) -> str:
        self._shelly.ensure_available()
        session_id = str(uuid.uuid4())
        now = int(self._clock())
        reserved_until = now + self._settings.payment_reservation_seconds

        if not self._sessions.reserve_device(
            self._settings.device_id,
            session_id,
            now,
            reserved_until,
        ):
            raise ShowerBusyError("Prysznic jest aktualnie zarezerwowany")

        session_persisted = False
        try:
            self._sessions.create_pending(
                session_id=session_id,
                device_id=self._settings.device_id,
                amount=self._settings.amount,
                customer_email=customer_email,
                expires_at=now + self._settings.session_ttl_seconds,
            )
            session_persisted = True
            redirect_url: str = self._payments.register(
                session_id=session_id,
                amount=self._settings.amount,
                customer_email=customer_email,
                return_url=(
                    f"{self._settings.frontend_base_url}/waiting.html?sessionId={session_id}"
                ),
                status_url=f"{self._settings.public_api_base_url}/webhook",
                description=(
                    f"Prysznic portowy nr 1, "
                    f"{self._settings.shower_duration_seconds // 60} minut"
                ),
            )
        except Exception:
            self._cleanup_failed_registration(session_id, now, session_persisted)
            raise

        log("Payment session created", {"sessionId": session_id})
        return redirect_url

    def process_webhook(self, payload: dict) -> None:
        session_id = payload["sessionId"]
        session = self._sessions.get(session_id)
        if not session:
            log("Webhook session not found", {"sessionId": session_id})
            return
        if session.get("amount") != payload["amount"]:
            log("Webhook amount mismatch", {"sessionId": session_id})
            return
        if session.get("status") == "active":
            return
        if not self._payments.verify(payload):
            log("Payment verification failed", {"sessionId": session_id})
            return

        now = int(self._clock())
        shower_ends_at = now + self._settings.shower_duration_seconds
        if not self._sessions.extend_device_reservation(
            self._settings.device_id,
            session_id,
            shower_ends_at,
        ):
            raise DeviceReservationLostError("Device reservation is no longer owned")

        activation_token = str(uuid.uuid4())
        claimed = self._sessions.claim_activation(
            session_id=session_id,
            activation_token=activation_token,
            now=now,
            lease_until=now + self._settings.activation_lease_seconds,
        )
        if not claimed:
            return

        try:
            self._shelly.activate()
            self._sessions.mark_active(
                session_id=session_id,
                activation_token=activation_token,
                shower_ends_at=shower_ends_at,
                expires_at=shower_ends_at + 3_600,
            )
        except Exception:
            self._sessions.mark_activation_failed(
                session_id=session_id,
                activation_token=activation_token,
                expires_at=now + 3_600,
            )
            raise

    def get_status(self, session_id: str) -> dict | None:
        session = self._sessions.get(session_id)
        if not session:
            return None
        return {"status": session["status"], "showerEndsAt": session.get("showerEndsAt")}

    def _cleanup_failed_registration(
        self, session_id: str, now: int, session_persisted: bool
    ) -> None:
        if session_persisted:
            try:
                self._sessions.mark_registration_failed(session_id, now + 3_600)
            except Exception as error:
                log("Failed to update registration state", {"errorType": type(error).__name__})
        try:
            self._sessions.release_device(self._settings.device_id, session_id)
        except Exception as error:
            log("Failed to release device reservation", {"errorType": type(error).__name__})
