class DeliveryAPIException(Exception):
    """Базове виключення транспортного шару API Укрпошти (network, timeout)."""


class UkrposhtaAPIException(Exception):
    """Помилка від сервера Укрпошти з повідомленням-описом."""

    def __init__(self, message=None, status_code=None, payload=None):
        self.message = message or ""
        self.status_code = status_code
        self.payload = payload
        super().__init__(self.message)


class TestEnvironmentWarning(Exception):
    """Маркерне виключення для попередження про тестове середовище."""
