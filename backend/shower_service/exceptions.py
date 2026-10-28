class ShowerUnavailableError(Exception):
    """The controller cannot be reached or its state cannot be read."""


class ShowerBusyError(Exception):
    """The shower is already active."""


class PaymentProviderUnavailableError(Exception):
    """Payment verification could not be completed due to a transient failure."""


class DeviceReservationLostError(Exception):
    """A paid session no longer owns the device reservation."""
