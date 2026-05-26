class NovaposhtaAPIException(Exception):
    def __init__(self, errors=None):
        self.errors = errors


class TestEnvironmentWarning(Exception):
    pass
