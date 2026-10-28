from typing import Any, cast

from botocore.exceptions import ClientError


class SessionRepository:
    def __init__(self, table):
        self._table = table

    def reserve_device(
        self,
        device_id: str,
        session_id: str,
        now: int,
        reserved_until: int,
    ) -> bool:
        try:
            self._table.put_item(
                Item={
                    "sessionId": self._device_key(device_id),
                    "status": "reserved",
                    "reservationId": session_id,
                    "lockUntil": reserved_until,
                    "ttl": reserved_until,
                },
                ConditionExpression="attribute_not_exists(sessionId) OR lockUntil < :now",
                ExpressionAttributeValues={":now": now},
            )
            return True
        except ClientError as error:
            if self._is_conditional_failure(error):
                return False
            raise

    def extend_device_reservation(
        self,
        device_id: str,
        session_id: str,
        reserved_until: int,
    ) -> bool:
        try:
            self._table.update_item(
                Key={"sessionId": self._device_key(device_id)},
                UpdateExpression="SET lockUntil = :until, #t = :until",
                ConditionExpression="reservationId = :reservation",
                ExpressionAttributeNames={"#t": "ttl"},
                ExpressionAttributeValues={
                    ":until": reserved_until,
                    ":reservation": session_id,
                },
            )
            return True
        except ClientError as error:
            if self._is_conditional_failure(error):
                return False
            raise

    def release_device(self, device_id: str, session_id: str) -> None:
        try:
            self._table.delete_item(
                Key={"sessionId": self._device_key(device_id)},
                ConditionExpression="reservationId = :reservation",
                ExpressionAttributeValues={":reservation": session_id},
            )
        except ClientError as error:
            if not self._is_conditional_failure(error):
                raise

    def create_pending(self, session_id, device_id, amount, customer_email, expires_at) -> None:
        self._table.put_item(
            Item={
                "sessionId": session_id,
                "deviceId": device_id,
                "amount": amount,
                "status": "pending",
                "mail": customer_email,
                "ttl": expires_at,
            }
        )

    def get(self, session_id: str) -> dict | None:
        result: dict[str, Any] = self._table.get_item(Key={"sessionId": session_id})
        return cast(dict | None, result.get("Item"))

    def mark_registration_failed(self, session_id: str, expires_at: int) -> None:
        self._table.update_item(
            Key={"sessionId": session_id},
            UpdateExpression="SET #s = :failed, #t = :ttl",
            ExpressionAttributeNames={"#s": "status", "#t": "ttl"},
            ExpressionAttributeValues={":failed": "registration_failed", ":ttl": expires_at},
        )

    def claim_activation(
        self,
        session_id: str,
        activation_token: str,
        now: int,
        lease_until: int,
    ) -> bool:
        try:
            self._table.update_item(
                Key={"sessionId": session_id},
                UpdateExpression=(
                    "SET #s = :activating, activationToken = :token, "
                    "activationLeaseUntil = :lease"
                ),
                ConditionExpression=(
                    "#s = :pending OR #s = :failed OR "
                    "(#s = :activating AND activationLeaseUntil < :now)"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":activating": "activating",
                    ":pending": "pending",
                    ":failed": "activation_failed",
                    ":token": activation_token,
                    ":lease": lease_until,
                    ":now": now,
                },
            )
            return True
        except ClientError as error:
            if self._is_conditional_failure(error):
                return False
            raise

    def mark_active(
        self,
        session_id: str,
        activation_token: str,
        shower_ends_at: int,
        expires_at: int,
    ) -> None:
        self._table.update_item(
            Key={"sessionId": session_id},
            UpdateExpression=(
                "SET #s = :active, showerEndsAt = :endsAt, #t = :ttl "
                "REMOVE activationToken, activationLeaseUntil"
            ),
            ConditionExpression="activationToken = :token",
            ExpressionAttributeNames={"#s": "status", "#t": "ttl"},
            ExpressionAttributeValues={
                ":active": "active",
                ":endsAt": shower_ends_at,
                ":ttl": expires_at,
                ":token": activation_token,
            },
        )

    def mark_activation_failed(
        self,
        session_id: str,
        activation_token: str,
        expires_at: int,
    ) -> None:
        self._table.update_item(
            Key={"sessionId": session_id},
            UpdateExpression=(
                "SET #s = :failed, #t = :ttl " "REMOVE activationToken, activationLeaseUntil"
            ),
            ConditionExpression="activationToken = :token",
            ExpressionAttributeNames={"#s": "status", "#t": "ttl"},
            ExpressionAttributeValues={
                ":failed": "activation_failed",
                ":ttl": expires_at,
                ":token": activation_token,
            },
        )

    @staticmethod
    def _device_key(device_id: str) -> str:
        return f"DEVICE#{device_id}"

    @staticmethod
    def _is_conditional_failure(error: ClientError) -> bool:
        return bool(error.response["Error"]["Code"] == "ConditionalCheckFailedException")
