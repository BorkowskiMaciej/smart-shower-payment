"""AWS Lambda entry point."""

from shower_service.bootstrap import build_handler

_handler = build_handler()


def lambda_handler(event, context):
    return _handler.handle(event, context)
