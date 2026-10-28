import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    shelly_auth_key: str
    device_id: str
    p24_merchant_id: int
    p24_pos_id: int
    p24_api_key: str
    p24_crc: str
    payment_base_url: str
    amount: int
    dynamodb_table: str
    frontend_base_url: str
    public_api_base_url: str
    shower_duration_seconds: int = 360
    session_ttl_seconds: int = 86_400
    payment_reservation_seconds: int = 900
    activation_lease_seconds: int = 30

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            shelly_auth_key=os.environ["SHELLY_AUTH_KEY"],
            device_id=os.environ["DEVICE_ID"],
            p24_merchant_id=int(os.environ["P24_MERCHANT_ID"]),
            p24_pos_id=int(os.environ["P24_POS_ID"]),
            p24_api_key=os.environ["P24_API_KEY"],
            p24_crc=os.environ["P24_CRC"],
            payment_base_url=os.environ["BASE_URL"].rstrip("/"),
            amount=int(os.environ["PRICE"]),
            dynamodb_table=os.environ.get("DYNAMODB_TABLE", "shower-sessions"),
            frontend_base_url=os.environ["FRONTEND_BASE_URL"].rstrip("/"),
            public_api_base_url=os.environ["PUBLIC_API_BASE_URL"].rstrip("/"),
            shower_duration_seconds=int(os.environ.get("SHOWER_DURATION_SECONDS", "360")),
            session_ttl_seconds=int(os.environ.get("SESSION_TTL_SECONDS", "86400")),
            payment_reservation_seconds=int(os.environ.get("PAYMENT_RESERVATION_SECONDS", "900")),
            activation_lease_seconds=int(os.environ.get("ACTIVATION_LEASE_SECONDS", "30")),
        )
