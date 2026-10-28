import boto3

from .config import Settings
from .handler import ApiHandler
from .payments import PaymentClient
from .repository import SessionRepository
from .service import ShowerService
from .shelly import ShellyClient


def build_handler() -> ApiHandler:
    settings = Settings.from_environment()
    table = boto3.resource("dynamodb").Table(settings.dynamodb_table)
    service = ShowerService(
        settings=settings,
        payments=PaymentClient(
            settings.p24_merchant_id,
            settings.p24_pos_id,
            settings.p24_api_key,
            settings.p24_crc,
            settings.payment_base_url,
        ),
        shelly=ShellyClient(settings.shelly_auth_key, settings.device_id),
        sessions=SessionRepository(table),
    )
    return ApiHandler(service, settings.frontend_base_url)
